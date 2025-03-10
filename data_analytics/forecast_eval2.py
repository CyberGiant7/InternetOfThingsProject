import numpy as np
import pandas as pd
from influxdb_client import InfluxDBClient
from pmdarima import auto_arima, ARIMA
import plotly.graph_objects as go
import plotly.io as pio
# from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Configura InfluxDB
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "uHnhErrBaY76NeLUWGjJfHTmooN0FibnAK1GTifGmqAYxRD6cWqVdsvtaQ_PD9G2i9fX9HasvUpXTin-KPiKoQ=="
INFLUXDB_ORG = "ProgettoIot"
INFLUXDB_BUCKET = "ProgettoIot"

# Connessione a InfluxDB
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()
measure_every_seconds = 30


# Funzione per ottenere i dati di temperatura
def get_temperature_data():
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
    |> range(start: -24h)
    |> filter(fn: (r) => r._measurement == "temperature" and r.location == "indoor")
    |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    |> keep(columns: ["_time", "value"])
    |> sort(columns: ["_time"])'''

    df = query_api.query_data_frame(query)
    if isinstance(df, list):
        df = df[0]  # InfluxDB potrebbe restituire una lista di dataframe

    df = df.rename(columns={"_time": "time", "value": "temperature"})
    df = df.set_index("time")
    df.index = pd.to_datetime(df.index)
    return df

def query_data():
    """
    Recupera gli ultimi 24 ore di dati per le temperature interna ed esterna
    e li unisce in un unico DataFrame.
    """
    # Nota: nel range puoi definire il periodo che preferisci
    query_indoor = f'''from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: -3h, stop: -1h)
                |> filter(fn: (r) => r._measurement == "temperature" and r.location == "indoor")
                |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> keep(columns: ["_time", "value"])
                '''
    query_outdoor = f'''from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: -3h, stop: -1h)
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

    df = df[['value_indoor', 'value_outdoor']]
    return df


# Otteniamo i dati
data = query_data()

# Definiamo le finestre temporali
errors = []
window_size = 30  # Minuti per la previsione
step = 30  # secondi tra un test e l'altro

for current_time in pd.date_range(start=data.index[0], end=data.index[-1] - pd.Timedelta(minutes=window_size), freq=f'{step}s'):

    # Filtro i dati fino al momento corrente
    train_data = data[data.index <= current_time]

    if len(train_data) < window_size//2:
        continue

    indoor_series = train_data['value_indoor']
    outdoor_series = train_data['value_outdoor']

    auto_model: ARIMA = auto_arima(
        indoor_series,
        exogenous=outdoor_series,
        seasonal=False,
        error_action='ignore',
        suppress_warnings=True,
        stepwise=True
    )

    # # Addestro il modello ARIMA
    # model = ARIMA(train_data["temperature"], order=(3, 1, 2))  # Ottimizza i parametri se necessario
    # model_fit = model.fit()

    # # Previsione per 30 minuti dopo
    exog_forecast = outdoor_series.iloc[-1:]  # per semplificare, usiamo l'ultimo valore anche per tutti gli step
    forecast = auto_model.predict(n_periods=60, X=exog_forecast, verbose=False)

    last_forecast = forecast.tail(1)


    # # Previsione per 30 minuti dopo
    # forecast = model_fit.forecast(steps=window_size)

    # Previsione per 30 minuti dopo
    # forecast = auto_model.forecast(steps=window_size).iloc[-1]


    # Valore reale
    # actual_time = current_time + pd.Timedelta(minutes=window_size)
    actual_time = last_forecast.index
    try:
        actual_value = data.loc[actual_time, "value_indoor"]
    except Exception as e:
        actual_value = None

    # add prediction to dataframe
    data.loc[actual_time, "forecast"] = last_forecast

    data.to_csv("forecast2.csv")

    print(f"Previsione per il {actual_time}: {last_forecast.iloc[0]}°C")
    print(f"Valore reale: {actual_value}°C")


    if actual_value is not None:
        error = abs(forecast - actual_value)
        errors.append(error)

# Valutazione del modello
mae = np.mean(errors)
mse = np.mean(np.array(errors) ** 2)
rmse = np.sqrt(mse)

print(f"Mean Absolute Error (MAE): {mae:.2f}°C")
print(f"Mean Squared Error (MSE): {mse:.2f}°C")
print(f"Root Mean Squared Error (RMSE): {rmse:.2f}°C")



pio.renderers.default = "browser"

fig = go.Figure()

fig.add_trace(go.Scatter(x=data.index, y=data["value_indoor"], name="Indoor Temperature"))
fig.add_trace(go.Scatter(x=data.index, y=data["value_outdoor"], name="Outdoor Temperature"))
fig.add_trace(go.Scatter(x=data.index, y=data["forecast"], name="Forecasted Indoor Temperature"))

fig.update_layout(title="Temperature Forecast", xaxis_title="Time", yaxis_title="Temperature (°C)")

client.close()
