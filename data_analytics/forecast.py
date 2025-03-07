import pandas as pd
import plotly.graph_objects as go
import math
import time
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_squared_error



# Configura InfluxDB
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "uHnhErrBaY76NeLUWGjJfHTmooN0FibnAK1GTifGmqAYxRD6cWqVdsvtaQ_PD9G2i9fX9HasvUpXTin-KPiKoQ=="
INFLUXDB_ORG = "ProgettoIot"
INFLUXDB_BUCKET = "ProgettoIot"

# Connessione a InfluxDB
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()


measure_every_seconds = 30
# Query per ottenere i dati dalla serie temporale
def get_data_from_influx(location):
    query = f'''from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: -1d)
                |> filter(fn: (r) => r._measurement == "temperature" and r.location == "{location}")
                |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> keep(columns: ["_time", "value"])
                '''
    result = query_api.query_data_frame(query)
    if result.empty:
        raise ValueError("Nessun dato disponibile in InfluxDB")
    result = result.rename(columns={"_time": "Date", "value": "Value"})
    result["Date"] = pd.to_datetime(result["Date"])
    result.set_index("Date", inplace=True)
    return result


# Funzione per addestrare e fare previsioni con ARIMA
def arima_forecast(history, steps=3, order=(1, 1, 1)):
    model = ARIMA(history, order=order)
    model_fit = model.fit()
    output = model_fit.forecast(steps=steps)
    return output


# Loop per eseguire il modello in real-time
threshold = 2.0  # Soglia di temperatura per il controllo spreco di energia
n_predictions = 10  # Numero di previsioni future
history_size = 500  # Dimensione dell'history
while True:
    try:
        df_indoor = get_data_from_influx("indoor")
        df_outdoor = get_data_from_influx("outdoor")

        # if len(df_indoor) < history_size or len(df_outdoor) < history_size:
        #     print(f"Attesa di almeno {history_size} campioni...")
        #     time.sleep(10)
        #     continue

        # history_indoor = df_indoor["Value"].iloc[-history_size:].tolist()
        # history_outdoor = df_outdoor["Value"].iloc[-history_size:].tolist()
        history_indoor = df_indoor["Value"].tolist()
        history_outdoor = df_outdoor["Value"].tolist()

        pred_indoor = arima_forecast(history_indoor, steps=n_predictions)
        pred_outdoor = arima_forecast(history_outdoor, steps=n_predictions)

        # actual_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for i in range(n_predictions):
            time_offset = measure_every_seconds * (i + 1)
            future_time = (df_indoor.last_valid_index() + timedelta(seconds=time_offset)).strftime("%Y-%m-%d %H:%M:%S")
            print(f"Data: {future_time} | Previsto Indoor: {pred_indoor[i]:.2f}°C | Previsto Outdoor: {pred_outdoor[i]:.2f}°C | Offset: {time_offset} secondi")

        print("")
        # print(f'Predicted Indoor: {pred_indoor}°C | Predicted Outdoor: {list(pred_outdoor)}°C')

        for i in range(n_predictions):
            diff = abs(pred_indoor[i] - pred_outdoor[i])
            time_offset = measure_every_seconds * (i + 1)
            if diff < threshold:
                print(f'⚠️ Possibile spreco energetico rilevato tra {time_offset} secondi! Differenza: {diff:.2f}°C')

        time.sleep(30)  # Attesa prima del prossimo ciclo
    except Exception as e:
        print(f"Errore: {e}")
        time.sleep(30)
