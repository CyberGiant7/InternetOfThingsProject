from flask import Flask, render_template, jsonify
import threading
import time
from datetime import timedelta
import pandas as pd
from influxdb_client import InfluxDBClient
from pmdarima import auto_arima
from performance_evaluation import PerformanceEvaluator

app = Flask(__name__)

# Configura InfluxDB
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "uHnhErrBaY76NeLUWGjJfHTmooN0FibnAK1GTifGmqAYxRD6cWqVdsvtaQ_PD9G2i9fX9HasvUpXTin-KPiKoQ=="
INFLUXDB_ORG = "ProgettoIot"
INFLUXDB_BUCKET = "ProgettoIot"

client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

# Variabili globali per i dati
latest_temperatures = {"indoor": None, "outdoor": None, "predictions": {}, "alert": "False"}
threshold = 1.0  # Differenza di temperatura per considerare uno spreco
measure_every_seconds = 30
forecast_horizon = 60

latest_temperatures = {
    "timestamps": [],
    "indoor": [],
    "outdoor": [],
    "predictions": [],
    "prediction_timestamps": [],
    "alert": False
}

# Inizializza il valutatore di prestazioni
performance_evaluator = PerformanceEvaluator()

# Variabili globali per le metriche di performance
performance_metrics = {
    "forecast_accuracy": {"mae": [], "mse": [], "rmse": [], "timestamps": []},
    "latency": {"values": [], "timestamps": []}
}


def query_data():
    """Recupera i dati più recenti da InfluxDB."""
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
    |> range(start: -3h)
    |> filter(fn: (r) => r._measurement == "temperature")
    |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
    |> pivot(rowKey:["_time"], columnKey: ["location"], valueColumn: "_value")
    |> keep(columns: ["_time", "indoor", "outdoor"])
    '''
    df = query_api.query_data_frame(query)
    df['_time'] = pd.to_datetime(df['_time']) + timedelta(hours=1)  # Aggiunta un'ora
    df.set_index('_time', inplace=True)
    df = df.asfreq(f'{measure_every_seconds}s')
    df = df.ffill()  # Gestione eventuali valori mancanti
    return df


def update_predictions():
    """Ciclo continuo per aggiornare le previsioni."""
    global latest_temperatures
    while True:
        df = query_data()
        if df.empty or len(df) < 10:
            time.sleep(60)
            continue

        indoor_series = df['indoor']
        outdoor_series = df['outdoor']

        try:
            # Utilizza auto_arima per determinare i migliori parametri (p, d, q)
            auto_model = auto_arima(
                indoor_series,
                exogenous=outdoor_series,
                seasonal=False,
                error_action='ignore',
                suppress_warnings=True,
                stepwise=True
            )

            exog_forecast = outdoor_series.iloc[-1:]  # per semplificare, usiamo l'ultimo valore anche per tutti gli step
            forecast = auto_model.predict(n_periods=60, X=exog_forecast)
            # print(forecast)
            last_time = df.index[-1]
            future_timestamps = [last_time + timedelta(seconds=measure_every_seconds * (i + 1)) for i in range(forecast_horizon)]

            latest_temperatures["timestamps"] = df.index.strftime('%Y-%m-%d %H:%M:%S').tolist()
            latest_temperatures["indoor"] = indoor_series.tolist()
            latest_temperatures["outdoor"] = outdoor_series.tolist()
            latest_temperatures["predictions"] = forecast.tolist()
            latest_temperatures["prediction_timestamps"] = [t.strftime('%Y-%m-%d %H:%M:%S') for t in future_timestamps]
            latest_temperatures["alert"] = str(any(abs(pred - indoor_series.iloc[-1]) > threshold for pred in forecast))
            #
            # latest_temperatures["indoor"] = indoor_series.iloc[-1]
            # latest_temperatures["outdoor"] = outdoor_series.iloc[-1]
            # latest_temperatures["predictions"] = forecast.to_dict()
            #
            # latest_temperatures["alert"] = str(abs(forecast.iloc[-1]- indoor_series.iloc[-1]) > threshold)
            print(latest_temperatures)
        except Exception as e:
            print("Errore durante la previsione:", e)

        time.sleep(10)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/data')
def get_data():
    return jsonify(latest_temperatures)


@app.route('/performance')
def get_performance():
    # Aggiorna le metriche di performance
    try:
        # Valuta l'accuratezza delle previsioni
        forecast_metrics = performance_evaluator.evaluate_forecast_accuracy()
        if forecast_metrics:
            performance_metrics["forecast_accuracy"] = {
                "mae": performance_evaluator.forecast_metrics["mae"],
                "mse": performance_evaluator.forecast_metrics["mse"],
                "rmse": performance_evaluator.forecast_metrics["rmse"],
                "timestamps": performance_evaluator.forecast_metrics["timestamps"]
            }
        
        # Ottieni i dati di latenza
        performance_metrics["latency"] = {
            "values": performance_evaluator.latency_metrics["latency_ms"],
            "timestamps": performance_evaluator.latency_metrics["timestamps"],
            "average": performance_evaluator.get_average_latency()
        }
        
        return jsonify(performance_metrics)
    except Exception as e:
        print(f"Errore durante il recupero delle metriche di performance: {e}")
        return jsonify({"error": str(e)})


if __name__ == '__main__':
    threading.Thread(target=update_predictions, daemon=True).start()
    app.run(debug=True)
