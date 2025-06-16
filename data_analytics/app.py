from flask import Flask, render_template, jsonify
import threading
import time
import warnings
from modules.database import InfluxDBManager
from modules.predictor import TemperaturePredictor
from modules.config import ANALYSIS_CONFIG
from modules.performance_evaluation import PerformanceEvaluator

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

# Update the performance_metrics structure
performance_metrics = {
    "forecast_accuracy": {
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
    },
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
            predictions = prediction_result["predictions"]
            prediction_timestamps = prediction_result["prediction_timestamps"]
            
            # Map indices to forecast horizons
            indices = {
                "1min": int(1 * 60 / ANALYSIS_CONFIG["measure_every_seconds"]) - 1,
                "10min": int(10 * 60 / ANALYSIS_CONFIG["measure_every_seconds"]) - 1,
                "20min": int(20 * 60 / ANALYSIS_CONFIG["measure_every_seconds"]) - 1,
                "30min": int(30 * 60 / ANALYSIS_CONFIG["measure_every_seconds"]) - 1
            }
            
            for horizon, idx in indices.items():
                if idx < len(predictions):
                    predicted_temp = predictions[idx]
                    timestamp = prediction_timestamps[idx]
                    db_manager.store_prediction(predicted_temp, timestamp, horizon)
                 
            if latest_temperatures["alert"] == "True":
                indoor_temp = prediction_result["indoor"][-1]
                predicted_temp = prediction_result["predictions"][-1]
                db_manager.log_alarm_event(indoor_temp, predicted_temp)
                
        time.sleep(10)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def get_data():
    return jsonify(latest_temperatures)

@app.route('/performance-data')
def get_performance():
    try:
        forecast_metrics = performance_evaluator.evaluate_forecast_accuracy()
        if forecast_metrics:
            # Update metrics for each horizon
            for horizon in ['1min', '10min', '20min', '30min']:
                if horizon in forecast_metrics:
                    performance_metrics["forecast_accuracy"][horizon] = {
                        "mae": performance_evaluator.forecast_metrics[horizon]["mae"],
                        "mse": performance_evaluator.forecast_metrics[horizon]["mse"],
                        "rmse": performance_evaluator.forecast_metrics[horizon]["rmse"],
                        "timestamps": performance_evaluator.forecast_metrics[horizon]["timestamps"]
                    }
        
        performance_metrics["latency"] = {
            "values": performance_evaluator.latency_metrics["latency_ms"],
            "timestamps": performance_evaluator.latency_metrics["timestamps"],
            "average": performance_evaluator.get_average_latency()
        }
        # return render_template('performance.html')
        return jsonify(performance_metrics)
    except Exception as e:
        print(f"Errore durante il recupero delle metriche di performance: {e}")
        return jsonify({"error": str(e)})
    
@app.route('/performance')
def performance():
    return render_template('performance.html')

if __name__ == '__main__':
    threading.Thread(target=update_predictions, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
