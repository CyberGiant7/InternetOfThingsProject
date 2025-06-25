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

# InfluxDB connection
client = InfluxDBClient(
    url=INFLUXDB_CONFIG["url"], 
    token=INFLUXDB_CONFIG["token"], 
    org=INFLUXDB_CONFIG["org"]
)
query_api = client.query_api()  # API for reading performance data
write_api = client.write_api()  # API for writing performance metrics

# Configuration parameters
measure_every_seconds = 30  # Sampling interval for data aggregation
PERFORMANCE_LOG_FILE = "performance_metrics.json"  # File to persist performance metrics


class PerformanceEvaluator:
    """
    Class for evaluating and monitoring IoT system performance.
    
    This class provides comprehensive performance analysis including:
    - ML model prediction accuracy evaluation
    - System latency monitoring
    - Historical performance tracking
    - Performance report generation
    - Metrics persistence and loading
    """
    
    def __init__(self):
        """
        Initialize performance evaluator with empty metrics structures.
        
        Sets up data structures to track forecast accuracy across different
        time horizons and system latency measurements over time.
        """
        # Initialize forecast accuracy metrics for different time horizons
        self.forecast_metrics = {
            "1min": {
                "mae": [],         # Mean Absolute Error values
                "mse": [],         # Mean Squared Error values
                "rmse": [],        # Root Mean Squared Error values
                "timestamps": []   # Timestamps for each measurement
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
        
        # Initialize latency tracking metrics
        self.latency_metrics = {
            "latency_ms": [],      # Latency measurements in milliseconds
            "timestamps": []       # Timestamps for latency measurements
        }
        
        # Load previously saved metrics if available
        self.load_metrics() 

    def load_metrics(self):
        """
        Load previously saved performance metrics from JSON file.
        
        This method restores historical performance data from persistent storage,
        allowing the system to maintain performance tracking across restarts.
        Handles missing or corrupted files gracefully.
        """
        try:
            # Attempt to load metrics from JSON file
            with open(PERFORMANCE_LOG_FILE, 'r') as f:
                data = json.load(f)
                # Restore forecast and latency metrics with fallback to defaults
                self.forecast_metrics = data.get('forecast_metrics', self.forecast_metrics)
                self.latency_metrics = data.get('latency_metrics', self.latency_metrics)
        except (FileNotFoundError, json.JSONDecodeError):
            # Handle missing or corrupted files using default empty metrics
            # This ensures the system continues to function even without historical data
            pass

    def save_metrics(self):
        """
        Save current performance metrics to JSON file for persistence.
        
        This method ensures that performance data is preserved across system
        restarts and provides a backup of historical performance measurements.
        """
        # Prepare data structure for JSON serialization
        data = {
            'forecast_metrics': self.forecast_metrics,
            'latency_metrics': self.latency_metrics
        }
        
        # Write metrics to JSON file with proper formatting
        with open(PERFORMANCE_LOG_FILE, 'w') as f:
            json.dump(data, f)

    def get_actual_value(self, timestamp):
        """
        Retrieve actual indoor temperature value from database for a specific timestamp.
        
        Args:
            timestamp (datetime/str): Target timestamp for temperature lookup
            
        Returns:
            float: Actual temperature value closest to the specified timestamp
            None: If no data is available for the timestamp
            
        This method finds the actual temperature measurement that corresponds
        to a prediction timestamp, enabling accuracy evaluation by comparing
        predicted vs actual values.
        """
        # Convert string to datetime if necessary
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        
        # Ensure timestamp is timezone-naive for consistent comparison
        if timestamp.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=None)

        # Define search window around target timestamp (±1 minute)
        start = (timestamp - timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        stop = (timestamp + timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')

        # Construct Flux query to find indoor temperature near target time
        query = f'''
        from(bucket: "{INFLUXDB_CONFIG["bucket"]}")
            |> range(start: {start}, stop: {stop})
            |> filter(fn: (r) => r._measurement == "temperature" and r.location == "indoor")
            |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            |> keep(columns: ["_time", "value"])
        '''
        
        # Execute query and get results
        df = query_api.query_data_frame(query)

        # Return None if no data found in the time window
        if df.empty:
            return None

        # Find the measurement closest to the target timestamp
        df['_time'] = pd.to_datetime(df['_time'])
        # Ensure database timestamps are timezone-naive for comparison
        df['_time'] = df['_time'].dt.tz_localize(None)
        # Calculate time difference from target timestamp
        df['time_diff'] = abs(df['_time'] - timestamp)
        # Find index of closest timestamp
        closest_idx = df['time_diff'].idxmin()
        
        # Return the temperature value at the closest timestamp
        return df.loc[closest_idx, 'value']

    def evaluate_forecast_accuracy(self, time_window_minutes=60):
        """
        Evaluate prediction accuracy by comparing forecasts with actual values.
        
        Args:
            time_window_minutes (int): Time window to analyze (default: 60 minutes)
            
        Returns:
            dict: Accuracy metrics for each forecast horizon (MAE, MSE, RMSE)
            None: If insufficient data is available
            
        This method performs comprehensive accuracy evaluation by:
        1. Retrieving all predictions from the specified time window
        2. Finding corresponding actual temperature values
        3. Calculating accuracy metrics for each forecast horizon
        4. Updating historical performance tracking
        """
        try:
            # Query all temperature predictions from the specified time window
            query = f'''
            from(bucket: "{INFLUXDB_CONFIG["bucket"]}")
                |> range(start: -{time_window_minutes}m)
                |> filter(fn: (r) => r._measurement == "temperature_predictions")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> keep(columns: ["_time", "predicted_temperature", "forecast_horizon"])
            '''
            df_predictions = query_api.query_data_frame(query)
            
            # Check if any predictions were found
            if df_predictions.empty:
                print("No predictions found in the specified time period.")
                return None

            # Convert timestamp strings to datetime objects
            df_predictions['_time'] = pd.to_datetime(df_predictions['_time'])
            
            # Process each forecast horizon separately for detailed analysis
            results = {}
            for horizon in ['1min', '10min', '20min', '30min']:
                print(f"\nProcessing predictions for {horizon} horizon...")
                
                # Filter predictions for current horizon
                horizon_predictions = df_predictions[df_predictions['forecast_horizon'] == horizon].copy()
                print(f"Found {len(horizon_predictions)} predictions for {horizon} horizon.")
                
                # Skip if no predictions found for this horizon
                if horizon_predictions.empty:
                    print(f"No predictions found for {horizon} horizon")
                    continue
                
                # Retrieve actual temperature values for each prediction timestamp
                actual_values = []
                for forecast_time in horizon_predictions['_time']:
                    actual_value = self.get_actual_value(forecast_time)
                    actual_values.append(actual_value)
                print(f"Found {len(actual_values)} actual values for {horizon} horizon.")
                
                # Add actual values to predictions dataframe
                horizon_predictions['actual_value'] = actual_values
                # Remove rows where actual values couldn't be found
                horizon_predictions.dropna(inplace=True)
                
                # Skip if no valid prediction-actual pairs found
                if horizon_predictions.empty:
                    continue
                
                # Calculate accuracy metrics using scikit-learn functions
                mae = mean_absolute_error(
                    horizon_predictions['actual_value'], 
                    horizon_predictions['predicted_temperature']
                )
                print(f"MAE for {horizon}: {mae:.2f}°C")
                
                mse = mean_squared_error(
                    horizon_predictions['actual_value'], 
                    horizon_predictions['predicted_temperature']
                )
                print(f"MSE for {horizon}: {mse:.2f}°C")
                
                rmse = np.sqrt(mse)  # Root Mean Squared Error
                print(f"RMSE for {horizon}: {rmse:.2f}°C")
                
                # Update historical metrics for this horizon
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Append new metrics to historical tracking
                self.forecast_metrics[horizon]["mae"].append(mae)
                self.forecast_metrics[horizon]["mse"].append(mse)
                self.forecast_metrics[horizon]["rmse"].append(rmse)
                self.forecast_metrics[horizon]["timestamps"].append(current_time)
                
                # Limit metrics history to prevent unlimited growth
                max_items = 1000  # Maximum number of historical metrics to keep
                if len(self.forecast_metrics[horizon]["timestamps"]) > max_items:
                    # Keep only the most recent metrics
                    for metric in ["mae", "mse", "rmse", "timestamps"]:
                        self.forecast_metrics[horizon][metric] = \
                            self.forecast_metrics[horizon][metric][-max_items:]
                
                # Store results for return value
                results[horizon] = {
                    "mae": mae,
                    "mse": mse,
                    "rmse": rmse
                }
                
                # Print detailed metrics for this horizon
                print(f"\nMetrics for {horizon} predictions:")
                print(f"Mean Absolute Error (MAE): {mae:.2f}°C")
                print(f"Mean Squared Error (MSE): {mse:.2f}°C")
                print(f"Root Mean Squared Error (RMSE): {rmse:.2f}°C")
            
            # Save updated metrics to persistent storage
            self.save_metrics()
            return results
            
        except Exception as e:
            # Log any errors during forecast evaluation
            print(f"Error during forecast evaluation: {e}")
            return None

    def get_average_latency(self, time_window_minutes=60):
        """
        Calculate average system latency over specified time window.
        
        Args:
            time_window_minutes (int): Time window for latency calculation
            
        Returns:
            float: Average latency in milliseconds
            None: If no latency data is available
            
        This method queries latency measurements from the database and
        calculates the mean response time for system performance monitoring.
        """
        # Construct Flux query to get average latency
        query = f'''
        from(bucket: "{INFLUXDB_CONFIG["bucket"]}")
            |> range(start: -{time_window_minutes}m)
            |> filter(fn: (r) => r._measurement == "latency")
            |> mean()
        '''
        
        # Execute query and extract average value
        result = query_api.query_data_frame(query)

        # Return average latency value if data is available
        if not result.empty and "_value" in result.columns:
            return result["_value"].iloc[0]
        return None