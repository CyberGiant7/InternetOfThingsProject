import os
import json
from flask import Flask, render_template, jsonify
import threading
import time
import warnings
from modules.database import InfluxDBManager
from modules.predictor import TemperaturePredictor
from modules.config import ANALYSIS_CONFIG, WEATHER_API_CONFIG
from modules.performance_evaluation import PerformanceEvaluator
from modules.weather_api import WeatherAPIClient
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv()

app = Flask(__name__)

# Initialize components
db_manager = InfluxDBManager()
predictor = TemperaturePredictor()
performance_evaluator = PerformanceEvaluator()
weather_api = WeatherAPIClient(city=WEATHER_API_CONFIG["city"], country_code=WEATHER_API_CONFIG["country_code"], api_key=WEATHER_API_CONFIG["api_key"])

STATUS_FILE = "hvac_status.json"

def get_hvac_status():
    """Read HVAC status from file."""
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r') as f:
                data = json.load(f)
                return data.get('hvac_status', False)
    except Exception:
        pass
    return False

# Global variables
latest_temperatures = {
    "timestamps": [],
    "indoor": [],
    "outdoor": [],
    "predictions": [],
    "prediction_timestamps": [],
    "api_data": {
        "temp_api": [],
        "temp_outdoor": [],
        "timestamp": [],
    },
    "alert": False,
    "hvac_active": False
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
        # Get sensor data
        df = db_manager.query_temperature_data(ANALYSIS_CONFIG["measure_every_seconds"])
        
        # Get weather API data
        api_weather = weather_api.get_current_weather()
        if api_weather:
            db_manager.store_api_weather_data(api_weather)
            
            try:
                weather_data = db_manager.query_api_weather_data(ANALYSIS_CONFIG["measure_every_seconds"])
            except Exception as e:
                print(f"Error querying API weather data: {e}")
                continue
            
            latest_temperatures["api_data"]["temp_api"].append(weather_data["temp_api"].to_list())
            latest_temperatures["api_data"]["temp_outdoor"].append(weather_data["temp_outdoor"].to_list())
            latest_temperatures["api_data"]["timestamp"].append([t.strftime("%Y-%m-%d %H:%M:%S") for t in weather_data["_time"].to_list()])
        
        # Get current HVAC status from file
        hvac_active = get_hvac_status()
        latest_temperatures["hvac_active"] = hvac_active
        
        # Continue with existing prediction logic
        prediction_result = predictor.predict(df, hvac_active)
        
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
                 
            # Only log alarm if HVAC is active and alert is True
            if latest_temperatures["alert"] == "True" and latest_temperatures["hvac_active"]:
                indoor_temp = prediction_result["indoor"][-1]
                predicted_temp = prediction_result["predictions"][-1]
                db_manager.log_alarm_event(indoor_temp, predicted_temp)
                
        time.sleep(10)

# Routes remain the same
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
        return jsonify(performance_metrics)
    except Exception as e:
        print(f"Error retrieving performance metrics: {e}")
        return jsonify({"error": str(e)})
    
@app.route('/performance')
def performance():
    return render_template('performance.html')

if __name__ == '__main__':
    # Start the prediction loop
    prediction_thread = threading.Thread(target=update_predictions, daemon=True)
    prediction_thread.start()
    
    # Run the Flask app
    app.run(host="0.0.0.0", port=5000, debug=True)
