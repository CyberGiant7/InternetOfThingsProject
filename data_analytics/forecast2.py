import time
from datetime import timedelta, datetime
import os
import csv

import pandas as pd
from influxdb_client import InfluxDBClient
from pmdarima import auto_arima

# Configura InfluxDB
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "uHnhErrBaY76NeLUWGjJfHTmooN0FibnAK1GTifGmqAYxRD6cWqVdsvtaQ_PD9G2i9fX9HasvUpXTin-KPiKoQ=="
INFLUXDB_ORG = "ProgettoIot"
INFLUXDB_BUCKET = "ProgettoIot"

# Connessione a InfluxDB
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

# Soglia per l'allarme
threshold = 1.0  # Differenza in gradi Celsius che indica uno spreco
measure_every_seconds = 30

# Nome del file in cui salvare le previsioni
FORECASTS_FILE = "forecasts.csv"

def save_forecast_row(forecast_timestamp, predicted_value, generation_time):
    """
    Salva una riga di previsione in un file CSV.
    forecast_timestamp: timestamp per cui è valida la previsione (stringa)
    predicted_value: valore previsto (float)
    generation_time: orario in cui la previsione è stata generata (stringa)
    """
    file_exists = os.path.isfile(FORECASTS_FILE)
    with open(FORECASTS_FILE, "a", newline="") as csvfile:
        fieldnames = ["forecast_timestamp", "predicted_value", "generation_time"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "forecast_timestamp": forecast_timestamp,
            "predicted_value": predicted_value,
            "generation_time": generation_time
        })

def query_data():
    """
    Recupera gli ultimi 24 ore di dati per le temperature interna ed esterna
    e li unisce in un unico DataFrame.
    """
    # Nota: nel range puoi definire il periodo che preferisci
    query_indoor = f'''from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: -24h)
                |> filter(fn: (r) => r._measurement == "temperature" and r.location == "indoor")
                |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> keep(columns: ["_time", "value"])
                '''
    query_outdoor = f'''from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: -24h)
                |> filter(fn: (r) => r._measurement == "temperature" and r.location == "outdoor")
                |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> keep(columns: ["_time", "value"])
                '''

    df_indoor = query_api.query_data_frame(query_indoor)
    df_outdoor = query_api.query_data_frame(query_outdoor)

    # Conversione del campo '_time' in datetime
    df_indoor['_time'] = pd.to_datetime(df_indoor['_time'])
    df_outdoor['_time'] = pd.to_datetime(df_outdoor['_time'])

    df_indoor.set_index('_time', inplace=True)
    df_outdoor.set_index('_time', inplace=True)

    df_indoor.sort_index(inplace=True)
    df_outdoor.sort_index(inplace=True)

    # Unione dei DataFrame usando merge_asof per allineare i timestamp
    df = pd.merge_asof(df_indoor, df_outdoor, left_index=True, right_index=True, suffixes=('_indoor', '_outdoor'))

    # Imposta la frequenza dell'indice per supportare il modello ARIMA
    df = df.asfreq(f'{measure_every_seconds}s')
    df = df.ffill()  # Gestione eventuali valori mancanti

    return df

def run_realtime_prediction():
    while True:
        # Recupera i dati aggiornati
        df = query_data()
        if df.empty or len(df) < 10:
            print("Dati insufficienti, attendo nuovi dati...")
            time.sleep(60)
            continue

        try:
            # Estrai le serie temporali: interna come endog, esterna come exog
            indoor_series = df['value_indoor']
            outdoor_series = df['value_outdoor']

            # Utilizza auto_arima per determinare i migliori parametri (p, d, q)
            auto_model = auto_arima(
                indoor_series,
                exogenous=outdoor_series,
                seasonal=False,
                error_action='ignore',
                suppress_warnings=True,
                stepwise=True
            )
            best_order = auto_model.order
            print(f"Parametri ARIMAX aggiornati: {best_order}")

            # Previsione per i prossimi 60 step (cioè 60 * measure_every_seconds secondi nel futuro)
            # In questo esempio usiamo auto_model per generare la previsione
            exog_forecast = outdoor_series.iloc[-1:]  # per semplificare, usiamo l'ultimo valore anche per tutti gli step
            forecast = auto_model.predict(n_periods=60, X=exog_forecast)
            forecast_generation_time = df.last_valid_index()  # tempo dell'ultimo dato reale
            forecast_generation_str = forecast_generation_time.strftime("%Y-%m-%d %H:%M:%S")

            # Salva ogni previsione con il relativo timestamp futuro
            for i in range(60):
                time_offset = measure_every_seconds * (i + 1)
                future_time = forecast_generation_time + timedelta(seconds=time_offset)
                future_time_str = future_time.strftime("%Y-%m-%d %H:%M:%S")
                predicted_val = forecast[i]
                save_forecast_row(future_time_str, predicted_val, forecast_generation_str)
                # Puoi anche stampare le previsioni se vuoi
                print(f"Data: {future_time_str} | Previsto Indoor: {predicted_val:.2f}°C | Generato: {forecast_generation_str}")

            # In questo esempio, prendo l'ultima previsione come riferimento per l'allarme
            predicted_value = forecast.iloc[-1]

            actual_value = indoor_series.iloc[-1]
            past_value = indoor_series.iloc[-60]
            diff_past = predicted_value - past_value
            diff = predicted_value - actual_value

            if diff > threshold:
                print("Attenzione: possibile spreco di calore rilevato!")
                print(f"Precedente: {past_value:.2f}°C, Attuale: {actual_value:.2f}°C,Previsione: {predicted_value:.2f}°C, Differenza: {diff:.2f}°C, Differenza precedente: {diff_past:.2f}°C")
                # Inserisci qui il codice per inviare un comando MQTT al dispositivo ESP32 o registrare l'evento su InfluxDB.
            else:
                print("Nessuno spreco rilevato.")
                print(f"Precedente: {past_value:.2f}°C, Attuale: {actual_value:.2f}°C,Previsione: {predicted_value:.2f}°C, Differenza: {diff:.2f}°C, Differenza precedente: {diff_past:.2f}°C")


        except Exception as e:
            print("Errore durante la previsione:", e)

        # Attende 120 secondi prima della prossima iterazione
        time.sleep(120)

if __name__ == '__main__':
    run_realtime_prediction()
