from datetime import timedelta

import pandas as pd
import numpy as np
from influxdb_client import InfluxDBClient
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Configura InfluxDB
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "uHnhErrBaY76NeLUWGjJfHTmooN0FibnAK1GTifGmqAYxRD6cWqVdsvtaQ_PD9G2i9fX9HasvUpXTin-KPiKoQ=="
INFLUXDB_ORG = "ProgettoIot"
INFLUXDB_BUCKET = "ProgettoIot"

# Nome del file CSV contenente le previsioni
FORECASTS_FILE = "forecasts.csv"

# Connessione a InfluxDB
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()
measure_every_seconds = 30


def get_actual_value(timestamp):
    """
    Recupera il valore reale della temperatura interna da InfluxDB per un determinato timestamp.
    """
    # convert str to datetime
    start = (pd.to_datetime(timestamp) - timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    stop = (pd.to_datetime(timestamp) + timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')

    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: {start}, stop: {stop})
        |> filter(fn: (r) => r._measurement == "temperature" and r.location == "indoor")
        |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> keep(columns: ["_time", "value"])
    '''
    df = query_api.query_data_frame(query)

    if df.empty:
        # print(f"Nessun dato trovato per il timestamp {timestamp}")
        return None

    # Filtra i dati per il timestamp specificato
    df = df[df['_time'] == timestamp]
    if df.empty:
        # print(f"Nessun dato trovato per il timestamp {timestamp}")
        return None

    return df['value'].iloc[0]  # Restituisce il primo valore disponibile


def evaluate_forecast_accuracy():
    """
    Valuta l'accuratezza delle previsioni confrontandole con i valori reali.
    """
    df_forecast = pd.read_csv(FORECASTS_FILE)
    df_forecast["forecast_timestamp"] = pd.to_datetime(df_forecast["forecast_timestamp"])

    actual_values = []
    for forecast_time in df_forecast["forecast_timestamp"]:
        actual_value = get_actual_value(forecast_time.strftime("%Y-%m-%dT%H:%M:%SZ"))
        actual_values.append(actual_value)

    df_forecast["actual_value"] = actual_values
    df_forecast.dropna(inplace=True)  # Rimuove i valori senza corrispondenza

    # Calcolo metriche di accuratezza
    mae = mean_absolute_error(df_forecast["actual_value"], df_forecast["predicted_value"])
    mse = mean_squared_error(df_forecast["actual_value"], df_forecast["predicted_value"])
    rmse = np.sqrt(mean_squared_error(df_forecast["actual_value"], df_forecast["predicted_value"]))

    print(f"Mean Absolute Error (MAE): {mae:.2f}°C")
    print(f"Mean Squared Error (MSE): {mse:.2f}°C")
    print(f"Root Mean Squared Error (RMSE): {rmse:.2f}°C")

    # Grafico
    import plotly.graph_objects as go
    import plotly.io as pio
    pio.renderers.default = "browser"

    # Rimuovi duplicati per il timestamp
    df_forecast_no_duplicates = df_forecast.drop_duplicates(subset=["forecast_timestamp"])

    fig = go.Figure()
    fig.add_trace(go.Line(x=df_forecast_no_duplicates["forecast_timestamp"], y=df_forecast_no_duplicates["actual_value"], name="Valori reali"))
    fig.add_trace(go.Scatter(x=df_forecast["forecast_timestamp"], y=df_forecast["predicted_value"], name="Previsioni", mode="markers"))
    fig.update_layout(title="Valori reali e previsioni", xaxis_title="Timestamp", yaxis_title="Temperatura (°C)")
    fig.show()
    client.close()



if __name__ == "__main__":
    try:
        evaluate_forecast_accuracy()
    except Exception as e:
        client.close()
        print(f"Errore durante l'evaluazione delle previsioni: {e}")