import time
from datetime import timedelta

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


def query_data():
    """
    Recupera gli ultimi 60 minuti di dati per le temperature interna ed esterna
    e li unisce in un unico DataFrame.
    """
    query_indoor = f'''from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: -24h, stop: 2025-03-07T15:15:00Z)
                |> filter(fn: (r) => r._measurement == "temperature" and r.location == "{'indoor'}")
                |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> keep(columns: ["_time", "value"])
                '''
    query_outdoor = f'''from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: -24h, stop: 2025-03-07T15:15:00Z)
                |> filter(fn: (r) => r._measurement == "temperature" and r.location == "{'outdoor'}")
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
    df = df.ffill()  # Opzionale: gestisce eventuali valori mancanti

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

            # Previsione: fornisci l'ultimo valore conosciuto della temperatura esterna come esogeno
            exog_forecast = outdoor_series.iloc[-1:]
            forecast = auto_model.predict(n_periods=60, X=exog_forecast)
            for i in range(60):
                time_offset = measure_every_seconds * (i + 1)
                future_time = (df.last_valid_index() + timedelta(seconds=time_offset)).strftime("%Y-%m-%d %H:%M:%S")
                print(f"Data: {future_time} | Previsto Indoor: {forecast.iloc[i]:.2f}°C | Offset: {time_offset} secondi")

            predicted_value = forecast.array[-1]

            # Ottieni l'ultimo valore reale della temperatura interna
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

        # Attende 60 secondi prima della prossima iterazione
        time.sleep(120)


if __name__ == '__main__':
    run_realtime_prediction()
