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
import datetime

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
    """
    Read HVAC (Heating, Ventilation, Air Conditioning) status from JSON file.
    
    Returns:
        bool: True if HVAC is active, False otherwise
    """
    try:
        # Check if status file exists before attempting to read
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r') as f:
                # Load JSON data and extract HVAC status
                data = json.load(f)
                return data.get('hvac_status', False)
    except Exception:
        # Return False if any error occurs during file reading
        pass
    return False

# Global data structure to store real-time temperature data and predictions
latest_temperatures = {
    "timestamps": [],           # Timestamps for sensor readings
    "indoor": [],              # Indoor temperature measurements
    "outdoor": [],             # Outdoor temperature measurements
    "predictions": [],         # Future temperature predictions
    "prediction_timestamps": [], # Timestamps for predictions
    "api_data": {              # Weather API data structure
        "temp_api": [],        # API temperature readings
        "temp_outdoor": [],    # Outdoor temperature from API
        "timestamp": [],       # API data timestamps
    },
    "alert": False,            # Alert status for temperature anomalies
    "hvac_active": False       # Current HVAC system status
}

# Performance metrics structure for tracking system accuracy and efficiency
performance_metrics = {
    "forecast_accuracy": {
        # Metrics for different prediction horizons (1, 10, 20, 30 minutes)
        "1min": {
            "mae": [],         # Mean Absolute Error values
            "mse": [],         # Mean Squared Error values
            "rmse": [],        # Root Mean Squared Error values
            "timestamps": []   # Timestamps for accuracy measurements
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
    "latency": {               # System response time metrics
        "values": [],          # Latency measurements in milliseconds
        "timestamps": []       # Timestamps for latency measurements
    }
}

def update_predictions():
    """
    Continuous background loop that updates temperature predictions and system data.
    This function runs in a separate thread and performs the following operations:
    1. Retrieves sensor data from database
    2. Fetches current weather data from external API
    3. Updates HVAC status from file
    4. Generates temperature predictions using ML model
    5. Stores predictions in database for different time horizons
    6. Logs alarm events when necessary
    """
    global latest_temperatures
    
    while True:
        # Retrieve historical temperature data from InfluxDB
        df = db_manager.query_temperature_data(ANALYSIS_CONFIG["measure_every_seconds"])
        
        # Fetch current weather data from external API
        api_weather = weather_api.get_current_weather()
        if api_weather:
            # Store API weather data in database
            db_manager.store_api_weather_data(api_weather)
            
            try:
                # Query stored API weather data
            
                weather_data = db_manager.query_api_weather_data(ANALYSIS_CONFIG["measure_every_seconds"])
                # Update global data structure with API weather information
                # Convert timezone (add 2 hours) and format timestamps
                latest_temperatures["api_data"]["temp_api"] = weather_data["temp_api"].to_list()
                latest_temperatures["api_data"]["temp_outdoor"] = weather_data["temp_outdoor"].to_list()
                latest_temperatures["api_data"]["timestamp"] = [
                    (t + datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S") 
                    for t in weather_data["_time"].to_list()
                ]
            except Exception as e:
                print(f"Error querying API weather data: {e}")
            
        
        # Read current HVAC status from file system
        hvac_active = get_hvac_status()
        latest_temperatures["hvac_active"] = hvac_active
        
        # Generate temperature predictions using ML model
        prediction_result = predictor.predict(df, hvac_active)
        
        if prediction_result:
            # Update global temperature data with new predictions
            latest_temperatures.update(prediction_result)
            predictions = prediction_result["predictions"]
            prediction_timestamps = prediction_result["prediction_timestamps"]
            
            # Calculate array indices for different forecast horizons
            # Convert time periods to array indices based on measurement frequency
            indices = {
                "1min": int(1 * 60 / ANALYSIS_CONFIG["measure_every_seconds"]) - 1,
                "10min": int(10 * 60 / ANALYSIS_CONFIG["measure_every_seconds"]) - 1,
                "20min": int(20 * 60 / ANALYSIS_CONFIG["measure_every_seconds"]) - 1,
                "30min": int(30 * 60 / ANALYSIS_CONFIG["measure_every_seconds"]) - 1
            }
            
            # Store predictions for each time horizon in database
            for horizon, idx in indices.items():
                if idx < len(predictions):
                    predicted_temp = predictions[idx]
                    timestamp = prediction_timestamps[idx]
                    db_manager.store_prediction(predicted_temp, timestamp, horizon)
                 
            # Log alarm events when temperature alert is active and HVAC is running
            # This helps track system performance during critical periods
            if latest_temperatures["alert"] == "True" and latest_temperatures["hvac_active"]:
                indoor_temp = prediction_result["indoor"][-1]     # Current indoor temperature
                predicted_temp = prediction_result["predictions"][-1]  # Latest prediction
                db_manager.log_alarm_event(indoor_temp, predicted_temp)
                
        # Wait 10 seconds before next update cycle
        time.sleep(10)

# Flask web application routes

@app.route('/')
def index():
    """
    Serve the main dashboard page.
    
    Returns:
        HTML template for the main temperature monitoring interface
    """
    return render_template('index.html')

@app.route('/data')
def get_data():
    """
    API endpoint to retrieve current temperature data and predictions.
    Used by frontend JavaScript to update charts and displays in real-time.
    
    Returns:
        JSON: Complete temperature data including sensors, predictions, and alerts
    """
    return jsonify(latest_temperatures)

@app.route('/performance-data')
def get_performance():
    """
    API endpoint to retrieve system performance metrics.
    Provides data for accuracy analysis and system monitoring.
    
    Returns:
        JSON: Performance metrics including forecast accuracy and system latency
    """
    try:
        # Evaluate current forecast accuracy across different time horizons
        forecast_metrics = performance_evaluator.evaluate_forecast_accuracy()
        
        if forecast_metrics:
            # Update performance metrics for each prediction horizon
            for horizon in ['1min', '10min', '20min', '30min']:
                if horizon in forecast_metrics:
                    performance_metrics["forecast_accuracy"][horizon] = {
                        "mae": performance_evaluator.forecast_metrics[horizon]["mae"],
                        "mse": performance_evaluator.forecast_metrics[horizon]["mse"],
                        "rmse": performance_evaluator.forecast_metrics[horizon]["rmse"],
                        "timestamps": performance_evaluator.forecast_metrics[horizon]["timestamps"]
                    }
        
        # Update latency metrics with current system response times
        performance_metrics["latency"] = {
            "values": performance_evaluator.latency_metrics["latency_ms"],
            "timestamps": performance_evaluator.latency_metrics["timestamps"],
            "average": performance_evaluator.get_average_latency()
        }
        
        return jsonify(performance_metrics)
    except Exception as e:
        # Return error information if performance evaluation fails
        print(f"Error retrieving performance metrics: {e}")
        return jsonify({"error": str(e)})
    
@app.route('/performance')
def performance():
    """
    Serve the performance monitoring dashboard page.
    
    Returns:
        HTML template for system performance analysis interface
    """
    return render_template('performance.html')

# Application entry point
if __name__ == '__main__':
    # Start the continuous prediction update loop in a separate daemon thread
    # Daemon thread ensures it terminates when main program exits
    prediction_thread = threading.Thread(target=update_predictions, daemon=True)
    prediction_thread.start()
    
    # Start the Flask web server
    # host="0.0.0.0" makes server accessible from any IP address
    # port=5000 is the default Flask port
    # debug=True enables auto-reload and detailed error messages
    app.run(host="0.0.0.0", port=5000, debug=True)
