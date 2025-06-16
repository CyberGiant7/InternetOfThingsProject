# Import necessary libraries for InfluxDB operations and data processing
from influxdb_client import InfluxDBClient, Point
import pandas as pd
from datetime import timedelta, datetime
from .config import INFLUXDB_CONFIG

class InfluxDBManager:
    """
    Manager class for handling all InfluxDB database operations.
    
    This class provides methods for:
    - Connecting to InfluxDB time-series database
    - Querying temperature sensor data
    - Storing ML predictions and weather API data
    - Logging system events and alarms
    - Managing time-series data aggregation and formatting
    """
    
    def __init__(self):
        """
        Initialize InfluxDB client and API connections.
        
        Sets up the database connection using configuration parameters
        and initializes query and write API clients for data operations.
        """
        # Create InfluxDB client with authentication credentials
        self.client = InfluxDBClient(
            url=INFLUXDB_CONFIG["url"],        # InfluxDB server URL
            token=INFLUXDB_CONFIG["token"],    # Authentication token
            org=INFLUXDB_CONFIG["org"]         # Organization name
        )
        # Initialize API clients for database operations
        self.query_api = self.client.query_api()  # For reading data
        self.write_api = self.client.write_api()  # For writing data
        self.bucket = INFLUXDB_CONFIG["bucket"]   # Database bucket name

    def query_temperature_data(self, measure_every_seconds):
        """
        Query historical temperature data from IoT sensors.
        
        Args:
            measure_every_seconds (int): Sampling interval for data aggregation
            
        Returns:
            DataFrame: Time-indexed temperature data with indoor/outdoor columns
            
        This method retrieves the last 3 hours of temperature measurements,
        aggregates them at the specified interval, and formats the data
        for machine learning model consumption.
        """
        # Construct Flux query to retrieve temperature sensor data
        query = f'''
        from(bucket: "{self.bucket}")
        |> range(start: -3h)                                    
        |> filter(fn: (r) => r._measurement == "temperature")
        |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
        |> pivot(rowKey:["_time"], columnKey: ["location"], valueColumn: "_value")
        |> keep(columns: ["_time", "indoor", "outdoor"])
        '''
        
        # Execute query and convert to DataFrame
        df = self.query_api.query_data_frame(query)
        
        # Adjust timezone (add 2 hours for local time)
        df['_time'] = pd.to_datetime(df['_time']) + timedelta(hours=2)
        
        # Set time column as index for time-series operations
        df.set_index('_time', inplace=True)
        
        # Ensure consistent time frequency for ML model
        df = df.asfreq(f'{measure_every_seconds}s')
        
        return df
    
    def store_prediction(self, predicted_temp, predicted_timestamp, forecast_horizon):
        """
        Store ML model temperature predictions in the database.
        
        Args:
            predicted_temp (float): Predicted temperature value
            predicted_timestamp (str): Timestamp for the prediction
            forecast_horizon (str): Time horizon of prediction (e.g., "10min", "30min")
            
        This method stores forecasted temperature values with their associated
        time horizons for later accuracy evaluation and system monitoring.
        """
        # Convert timestamp string to datetime object and adjust timezone
        timestamp = datetime.strptime(predicted_timestamp, "%Y-%m-%d %H:%M:%S") - timedelta(hours=2)
        
        # Create InfluxDB point with prediction data
        point = Point("temperature_predictions") \
            .tag("forecast_horizon", forecast_horizon) \
            .field("predicted_temperature", predicted_temp) \
            .time(timestamp)
        
        # Write prediction to database
        self.write_api.write(bucket=self.bucket, record=point)

    def log_alarm_event(self, indoor_temp, predicted_temp):
        """
        Log temperature alarm events for system monitoring.
        
        Args:
            indoor_temp (float): Current indoor temperature
            predicted_temp (float): Predicted temperature that triggered alarm
            
        This method records instances when the temperature prediction system
        detects anomalies or triggers HVAC control actions, helping track
        system performance and energy efficiency.
        """
        # Create InfluxDB point with alarm event data
        point = Point("temperature_alarms") \
            .field("indoor_temperature", indoor_temp) \
            .field("predicted_temperature", predicted_temp) \
            .field("temperature_difference", abs(predicted_temp - indoor_temp))  # Calculate prediction error
        
        # Write alarm event to database with current timestamp
        self.write_api.write(bucket=self.bucket, record=point)

    def store_api_weather_data(self, weather_data):
        """
        Store weather data from external API to the database.
        
        Args:
            weather_data (dict): Weather data from external API containing:
                - temperature: Current temperature
                - humidity: Current humidity
                - timestamp: Data timestamp
                
        This method persists external weather data for correlation analysis
        with indoor temperature patterns and prediction model enhancement.
        """
        try:
            # Validate input data
            if not weather_data:
                return
                
            # Create InfluxDB point with weather API data
            point = Point("weather_api_data") \
                .field("temperature", float(weather_data["temperature"])) \
                .field("humidity", float(weather_data["humidity"])) \
                .tag("source", "external_api") \
                .time(weather_data["timestamp"], write_precision="ms")  # Use millisecond precision
            
            # Write weather data to database
            self.write_api.write(bucket=self.bucket, record=point)
            print(f"API weather data stored: {weather_data['temperature']}°C at {weather_data['timestamp']}")
            
        except Exception as e:
            # Log any errors during weather data storage
            print(f"Error storing API weather data: {e}")
            
    def query_api_weather_data(self, measure_every_seconds):
        """
        Query recent weather API data and correlate with outdoor sensor data.
        
        Args:
            measure_every_seconds (int): Sampling interval for data aggregation
            
        Returns:
            DataFrame: Merged weather data with outdoor sensor and API temperatures
            None: If no data is available
            
        This method performs a complex query that joins outdoor sensor data
        with external weather API data to provide comprehensive environmental
        context for the temperature prediction system.
        """        
        # Construct complex Flux query with multiple data sources and joins
        query = f'''
            outdoor = 
            from(bucket: "{self.bucket}")
                |> range(start: -3h)
                |> filter(fn: (r) =>
                    r._measurement == "temperature" and
                    r._field       == "value"       and
                    r.location     == "outdoor"
                )
                |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
                |> keep(columns: ["_time", "_value"])
                |> rename(columns: {{_value: "temp_outdoor"}})
                
            external = 
            from(bucket: "ProgettoIot")
                |> range(start: -3h)
                |> filter(fn: (r) =>
                    r._measurement == "weather_api_data" and
                    r._field       == "temperature"
                )
                |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
                |> keep(columns: ["_time", "_value"])
                |> rename(columns: {{_value: "temp_api"}})

            join(
            tables: {{out: outdoor, ext: external}},
            on: ["_time"],
            method: "inner"
            )
            |> keep(columns: ["_time", "temp_outdoor", "temp_api"])
            |> yield(name: "merged_temps")
        '''
        
        # Execute the complex join query
        result = self.query_api.query_data_frame(query)
        
        # Return None if no data is available
        if result.empty:
            return None
            
        return result
