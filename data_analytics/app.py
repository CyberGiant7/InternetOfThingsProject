from flask import Flask, render_template, jsonify
import threading
import time
import warnings
from modules.database import InfluxDBManager
from modules.predictor import TemperaturePredictor
from modules.config import ANALYSIS_CONFIG
from performance_evaluation import PerformanceEvaluator

warnings.filterwarnings("ignore")

app = Flask(__name__)

# Initialize components
db_manager = InfluxDBManager()
predictor = TemperaturePredictor()
performance_evaluator = PerformanceEvaluator()

# Global variables
latest_temperatures = {
    "timestamps": [],
    "indoor": [],
    "outdoor": [],
    "predictions": [],
    "prediction_timestamps": [],
    "alert": False
}

performance_metrics = {
    "forecast_accuracy": {"mae": [], "mse": [], "rmse": [], "timestamps": []},
    "latency": {"values": [], "timestamps": []}
}

def update_predictions():
    """Continuous prediction update loop."""
    global latest_temperatures
    while True:
        df = db_manager.query_temperature_data(ANALYSIS_CONFIG["measure_every_seconds"])
        prediction_result = predictor.predict(df)
        if prediction_result:
            latest_temperatures.update(prediction_result)
        time.sleep(10)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def get_data():
    return jsonify(latest_temperatures)

@app.route('/performance')
def get_performance():
    try:
        forecast_metrics = performance_evaluator.evaluate_forecast_accuracy()
        if forecast_metrics:
            performance_metrics["forecast_accuracy"] = {
                "mae": performance_evaluator.forecast_metrics["mae"],
                "mse": performance_evaluator.forecast_metrics["mse"],
                "rmse": performance_evaluator.forecast_metrics["rmse"],
                "timestamps": performance_evaluator.forecast_metrics["timestamps"]
            }
        
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
    app.run(host="0.0.0.0", port=5000, debug=True)
