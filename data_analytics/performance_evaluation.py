import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient, Point
from sklearn.metrics import mean_absolute_error, mean_squared_error
import plotly.graph_objects as go
import plotly.io as pio
import json

# Configurazione InfluxDB
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "uHnhErrBaY76NeLUWGjJfHTmooN0FibnAK1GTifGmqAYxRD6cWqVdsvtaQ_PD9G2i9fX9HasvUpXTin-KPiKoQ=="
INFLUXDB_ORG = "ProgettoIot"
INFLUXDB_BUCKET = "ProgettoIot"

# Connessione a InfluxDB
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()
write_api = client.write_api()

# Parametri di configurazione
measure_every_seconds = 30
FORECASTS_FILE = "forecasts.csv"
PERFORMANCE_LOG_FILE = "performance_metrics.json"


class PerformanceEvaluator:
    def __init__(self):
        self.forecast_metrics = {
            "mae": [],
            "mse": [],
            "rmse": [],
            "timestamps": []
        }
        self.latency_metrics = {
            "latency_ms": [],
            "timestamps": []
        }
        self.load_metrics()

    def load_metrics(self):
        """Carica le metriche salvate dal file JSON se esiste."""
        try:
            with open(PERFORMANCE_LOG_FILE, 'r') as f:
                data = json.load(f)
                self.forecast_metrics = data.get('forecast_metrics', self.forecast_metrics)
                self.latency_metrics = data.get('latency_metrics', self.latency_metrics)
        except (FileNotFoundError, json.JSONDecodeError):
            # Il file non esiste o è corrotto, usa i valori predefiniti
            pass

    def save_metrics(self):
        """Salva le metriche correnti in un file JSON."""
        data = {
            'forecast_metrics': self.forecast_metrics,
            'latency_metrics': self.latency_metrics
        }
        with open(PERFORMANCE_LOG_FILE, 'w') as f:
            json.dump(data, f)

    def get_actual_value(self, timestamp):
        """Recupera il valore reale della temperatura interna da InfluxDB per un determinato timestamp."""
        # Converti stringa in datetime se necessario
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        
        # Assicurati che il timestamp sia timezone-naive
        if timestamp.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=None)

        start = (timestamp - timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        stop = (timestamp + timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')

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
            return None

        # Trova il timestamp più vicino
        df['_time'] = pd.to_datetime(df['_time'])
        # Assicurati che i timestamp di InfluxDB siano timezone-naive
        df['_time'] = df['_time'].dt.tz_localize(None)
        df['time_diff'] = abs(df['_time'] - timestamp)
        closest_idx = df['time_diff'].idxmin()
        return df.loc[closest_idx, 'value']

    def evaluate_forecast_accuracy(self, forecasts_file=FORECASTS_FILE):
        """Valuta l'accuratezza delle previsioni confrontandole con i valori reali."""
        try:
            df_forecast = pd.read_csv(forecasts_file)
            df_forecast["forecast_timestamp"] = pd.to_datetime(df_forecast["forecast_timestamp"])

            actual_values = []
            for forecast_time in df_forecast["forecast_timestamp"]:
                actual_value = self.get_actual_value(forecast_time)
                actual_values.append(actual_value)

            df_forecast["actual_value"] = actual_values
            df_forecast.dropna(inplace=True)  # Rimuove i valori senza corrispondenza

            if df_forecast.empty:
                print("Nessun dato valido per la valutazione delle previsioni.")
                return None

            # Calcolo metriche di accuratezza
            mae = mean_absolute_error(df_forecast["actual_value"], df_forecast["predicted_value"])
            mse = mean_squared_error(df_forecast["actual_value"], df_forecast["predicted_value"])
            rmse = np.sqrt(mse)

            # Aggiorna le metriche
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.forecast_metrics["mae"].append(mae)
            self.forecast_metrics["mse"].append(mse)
            self.forecast_metrics["rmse"].append(rmse)
            self.forecast_metrics["timestamps"].append(current_time)

            # Limita la dimensione delle liste a 1000 elementi
            max_items = 1000
            if len(self.forecast_metrics["timestamps"]) > max_items:
                self.forecast_metrics["mae"] = self.forecast_metrics["mae"][-max_items:]
                self.forecast_metrics["mse"] = self.forecast_metrics["mse"][-max_items:]
                self.forecast_metrics["rmse"] = self.forecast_metrics["rmse"][-max_items:]
                self.forecast_metrics["timestamps"] = self.forecast_metrics["timestamps"][-max_items:]

            self.save_metrics()

            print(f"Mean Absolute Error (MAE): {mae:.2f}°C")
            print(f"Mean Squared Error (MSE): {mse:.2f}°C")
            print(f"Root Mean Squared Error (RMSE): {rmse:.2f}°C")

            return {
                "mae": mae,
                "mse": mse,
                "rmse": rmse
            }

        except Exception as e:
            print(f"Errore durante la valutazione delle previsioni: {e}")
            return None

    def record_data_latency(self, device_timestamp, received_timestamp=None):
        """Registra la latenza tra l'invio dei dati dal dispositivo e la ricezione nel proxy."""
        if received_timestamp is None:
            received_timestamp = datetime.now()

        # Calcola la latenza in millisecondi
        if isinstance(device_timestamp, str):
            device_timestamp = pd.to_datetime(device_timestamp)
            
        # Assicurati che entrambi i timestamp abbiano lo stesso stato di timezone
        if device_timestamp.tzinfo is not None and received_timestamp.tzinfo is None:
            received_timestamp = received_timestamp.replace(tzinfo=device_timestamp.tzinfo)
        elif device_timestamp.tzinfo is None and received_timestamp.tzinfo is not None:
            device_timestamp = device_timestamp.replace(tzinfo=received_timestamp.tzinfo)
        # Oppure rendi entrambi timezone-naive
        elif device_timestamp.tzinfo is not None and received_timestamp.tzinfo is not None:
            device_timestamp = device_timestamp.replace(tzinfo=None)
            received_timestamp = received_timestamp.replace(tzinfo=None)

        latency_ms = (received_timestamp - device_timestamp).total_seconds() * 1000

        # Registra la latenza in InfluxDB
        point = Point("performance").tag("metric", "latency").field("value", latency_ms)
        write_api.write(bucket=INFLUXDB_BUCKET, record=point)

        # Aggiorna le metriche locali
        current_time = received_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        self.latency_metrics["latency_ms"].append(latency_ms)
        self.latency_metrics["timestamps"].append(current_time)

        # Limita la dimensione delle liste a 1000 elementi
        max_items = 1000
        if len(self.latency_metrics["timestamps"]) > max_items:
            self.latency_metrics["latency_ms"] = self.latency_metrics["latency_ms"][-max_items:]
            self.latency_metrics["timestamps"] = self.latency_metrics["timestamps"][-max_items:]

        self.save_metrics()

        return latency_ms

    def get_average_latency(self, time_window_minutes=60):
        """Calcola la latenza media nell'ultima ora (o nel periodo specificato)."""
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -{time_window_minutes}m)
            |> filter(fn: (r) => r._measurement == "performance" and r.metric == "latency")
            |> mean()
        '''
        result = query_api.query_data_frame(query)

        if result.empty:
            # Se non ci sono dati in InfluxDB, usa i dati locali
            if not self.latency_metrics["latency_ms"]:
                return None

            # Filtra per l'ultima ora
            now = datetime.now()
            cutoff = now - timedelta(minutes=time_window_minutes)
            recent_timestamps = []
            recent_latencies = []

            for i, ts_str in enumerate(self.latency_metrics["timestamps"]):
                ts = pd.to_datetime(ts_str)
                if ts >= cutoff:
                    recent_timestamps.append(ts_str)
                    recent_latencies.append(self.latency_metrics["latency_ms"][i])

            if not recent_latencies:
                return None

            return sum(recent_latencies) / len(recent_latencies)
        else:
            return result["_value"].iloc[0]

    def plot_forecast_accuracy(self):
        """Genera un grafico dell'accuratezza delle previsioni nel tempo."""
        if not self.forecast_metrics["timestamps"]:
            print("Nessun dato disponibile per il grafico.")
            return

        pio.renderers.default = "browser"

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=self.forecast_metrics["timestamps"], y=self.forecast_metrics["mae"], name="MAE"))
        fig.add_trace(go.Scatter(x=self.forecast_metrics["timestamps"], y=self.forecast_metrics["rmse"], name="RMSE"))

        fig.update_layout(
            title="Accuratezza delle previsioni nel tempo",
            xaxis_title="Data/Ora",
            yaxis_title="Errore (°C)",
            legend_title="Metriche"
        )

        fig.show()

    def plot_latency(self):
        """Genera un grafico della latenza di rete nel tempo."""
        if not self.latency_metrics["timestamps"]:
            print("Nessun dato disponibile per il grafico.")
            return

        pio.renderers.default = "browser"

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=self.latency_metrics["timestamps"],
            y=self.latency_metrics["latency_ms"],
            name="Latenza"
        ))

        fig.update_layout(
            title="Latenza di rete nel tempo",
            xaxis_title="Data/Ora",
            yaxis_title="Latenza (ms)"
        )

        fig.show()

    def generate_performance_report(self):
        """Genera un report completo sulle prestazioni del sistema."""
        # Valuta l'accuratezza delle previsioni
        forecast_metrics = self.evaluate_forecast_accuracy()

        # Calcola la latenza media
        avg_latency = self.get_average_latency()

        # Prepara il report
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "forecast_accuracy": forecast_metrics if forecast_metrics else "Dati insufficienti",
            "average_latency_ms": avg_latency if avg_latency else "Dati insufficienti"
        }

        print("\n===== REPORT PRESTAZIONI SISTEMA =====")
        print(f"Data/Ora: {report['timestamp']}")
        print("\nAccuratezza previsioni:")
        if isinstance(report['forecast_accuracy'], dict):
            print(f"  MAE: {report['forecast_accuracy']['mae']:.2f}°C")
            print(f"  MSE: {report['forecast_accuracy']['mse']:.2f}°C")
            print(f"  RMSE: {report['forecast_accuracy']['rmse']:.2f}°C")
        else:
            print(f"  {report['forecast_accuracy']}")

        print("\nLatenza di rete:")
        if isinstance(report['average_latency_ms'], (int, float)):
            print(f"  Media: {report['average_latency_ms']:.2f} ms")
        else:
            print(f"  {report['average_latency_ms']}")

        return report


# Esempio di utilizzo
if __name__ == "__main__":
    evaluator = PerformanceEvaluator()
    
    # Genera un report completo
    evaluator.generate_performance_report()
    
    # Visualizza i grafici
    evaluator.plot_forecast_accuracy()
    evaluator.plot_latency()