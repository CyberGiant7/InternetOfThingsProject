import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient, Point
from sklearn.metrics import mean_absolute_error, mean_squared_error
import plotly.graph_objects as go
import plotly.io as pio
import json
from modules.config import INFLUXDB_CONFIG

# Connessione a InfluxDB
client = InfluxDBClient(url=INFLUXDB_CONFIG["url"], token=INFLUXDB_CONFIG["token"], org=INFLUXDB_CONFIG["org"])
query_api = client.query_api()
write_api = client.write_api()

# Parametri di configurazione
measure_every_seconds = 30
FORECASTS_FILE = "forecasts.csv"
PERFORMANCE_LOG_FILE = "performance_metrics.json"


class PerformanceEvaluator:
    def __init__(self):
        self.forecast_metrics = {
            "1min": {
                "mae": [],
                "mse": [],
                "rmse": [],
                "timestamps": []
            },
            "10min": {
                "mae": [],
                "mse": [],
                "rmse": [],
                "timestamps": []
            },
            "20min": {
                "mae": [],
                "mse": [],
                "rmse": [],
                "timestamps": []
            },
            "30min": {
                "mae": [],
                "mse": [],
                "rmse": [],
                "timestamps": []
            }
        }
        self.latency_metrics = {
            "latency_ms": [],
            "timestamps": []
        }
        # self.load_metrics()

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
        from(bucket: "{INFLUXDB_CONFIG["bucket"]}")
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

    def evaluate_forecast_accuracy(self, time_window_minutes=60):
        """Valuta l'accuratezza delle previsioni confrontandole con i valori reali per ogni orizzonte temporale."""
        try:
            # Query predictions from InfluxDB
            query = f'''
            from(bucket: "{INFLUXDB_CONFIG["bucket"]}")
                |> range(start: -{time_window_minutes}m)
                |> filter(fn: (r) => r._measurement == "temperature_predictions")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> keep(columns: ["_time", "predicted_temperature", "forecast_horizon"])
            '''
            df_predictions = query_api.query_data_frame(query)
            
            if df_predictions.empty:
                print("Nessuna previsione trovata nel periodo specificato.")
                return None

            # Convert timestamps
            df_predictions['_time'] = pd.to_datetime(df_predictions['_time'])
            
            # Process each forecast horizon separately
            results = {}
            for horizon in ['1min', '10min', '20min', '30min']:
                print(f"\nProcessing predictions for {horizon} horizon...")
                horizon_predictions = df_predictions[df_predictions['forecast_horizon'] == horizon].copy()
                print(f"Found {len(horizon_predictions)} predictions for {horizon} horizon.")
                if horizon_predictions.empty:
                    print(f"Nessuna previsione trovata per l'orizzonte {horizon}")
                    continue
                
                # Get actual values for this horizon's predictions
                actual_values = []
                for forecast_time in horizon_predictions['_time']:
                    actual_value = self.get_actual_value(forecast_time)
                    actual_values.append(actual_value)
                print(f"Found {len(actual_values)} actual values for {horizon} horizon.")
                
                horizon_predictions['actual_value'] = actual_values
                horizon_predictions.dropna(inplace=True)
                
                if horizon_predictions.empty:
                    continue
                
                # Calculate metrics for this horizon
                mae = mean_absolute_error(horizon_predictions['actual_value'], 
                                        horizon_predictions['predicted_temperature'])
                print(f"MAE for {horizon}: {mae:.2f}°C")
                mse = mean_squared_error(horizon_predictions['actual_value'], 
                                       horizon_predictions['predicted_temperature'])
                print(f"MSE for {horizon}: {mse:.2f}°C")
                rmse = np.sqrt(mse)
                print(f"RMSE for {horizon}: {rmse:.2f}°C")
                
                # Update metrics for this horizon
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(self.forecast_metrics)
                self.forecast_metrics[horizon]["mae"].append(mae)
                print(self.forecast_metrics[horizon]["mae"])
                self.forecast_metrics[horizon]["mse"].append(mse)
                self.forecast_metrics[horizon]["rmse"].append(rmse)
                self.forecast_metrics[horizon]["timestamps"].append(current_time)
                
                # Limit metrics history
                max_items = 1000
                if len(self.forecast_metrics[horizon]["timestamps"]) > max_items:
                    for metric in ["mae", "mse", "rmse", "timestamps"]:
                        self.forecast_metrics[horizon][metric] = \
                            self.forecast_metrics[horizon][metric][-max_items:]
                
                results[horizon] = {
                    "mae": mae,
                    "mse": mse,
                    "rmse": rmse
                }
                
                print(f"\nMetriche per previsioni a {horizon}:")
                print(f"Mean Absolute Error (MAE): {mae:.2f}°C")
                print(f"Mean Squared Error (MSE): {mse:.2f}°C")
                print(f"Root Mean Squared Error (RMSE): {rmse:.2f}°C")
            
            self.save_metrics()
            return results
            
        except Exception as e:
            print(f"Errore durante la valutazione delle previsioni: {e}")
            return None

    

    def get_average_latency(self, time_window_minutes=60):
        """Calcola la latenza media nell'ultima ora (o nel periodo specificato)."""
        query = f'''
        from(bucket: "{INFLUXDB_CONFIG["bucket"]}")
            |> range(start: -{time_window_minutes}m)
            |> filter(fn: (r) => r._measurement == "latency")
            |> mean()
        '''
        result = query_api.query_data_frame(query)

        return result["_value"].iloc[0]

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
            for horizon, metrics in report['forecast_accuracy'].items():
                print(f"\nOrizzonte {horizon}:")
                print(f"  MAE: {metrics['mae']:.2f}°C")
                print(f"  MSE: {metrics['mse']:.2f}°C")
                print(f"  RMSE: {metrics['rmse']:.2f}°C")
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