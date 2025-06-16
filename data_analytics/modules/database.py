from influxdb_client import InfluxDBClient, Point
import pandas as pd
from datetime import timedelta, datetime
from .config import INFLUXDB_CONFIG

class InfluxDBManager:
    def __init__(self):
        self.client = InfluxDBClient(
            url=INFLUXDB_CONFIG["url"],
            token=INFLUXDB_CONFIG["token"],
            org=INFLUXDB_CONFIG["org"]
        )
        self.query_api = self.client.query_api()
        self.write_api = self.client.write_api()
        self.bucket = INFLUXDB_CONFIG["bucket"]

    def query_temperature_data(self, measure_every_seconds):
        query = f'''
        from(bucket: "{self.bucket}")
        |> range(start: -3h)
        |> filter(fn: (r) => r._measurement == "temperature")
        |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
        |> pivot(rowKey:["_time"], columnKey: ["location"], valueColumn: "_value")
        |> keep(columns: ["_time", "indoor", "outdoor"])
        '''
        df = self.query_api.query_data_frame(query)
        df['_time'] = pd.to_datetime(df['_time']) + timedelta(hours=2)
        df.set_index('_time', inplace=True)
        df = df.asfreq(f'{measure_every_seconds}s')
        return df
    
    def store_prediction(self, predicted_temp, predicted_timestamp, forecast_horizon):
        timestamp = datetime.strptime(predicted_timestamp, "%Y-%m-%d %H:%M:%S") - timedelta(hours=2)
        
        point = Point("temperature_predictions") \
            .tag("forecast_horizon", forecast_horizon) \
            .field("predicted_temperature", predicted_temp) \
            .time(timestamp)
        
        self.write_api.write(bucket=self.bucket, record=point)

    def log_alarm_event(self, indoor_temp, predicted_temp):
        point = Point("temperature_alarms") \
            .field("indoor_temperature", indoor_temp) \
            .field("predicted_temperature", predicted_temp) \
            .field("temperature_difference", abs(predicted_temp - indoor_temp))
        
        self.write_api.write(bucket=self.bucket, record=point)

    def store_api_weather_data(self, weather_data):
        """
        Store weather data from external API to the database.
        
        Args:
            weather_data (dict): Weather data from the API
        """
        try:
            if not weather_data:
                return
                
            point = Point("weather_api_data") \
                .field("temperature", float(weather_data["temperature"])) \
                .field("humidity", float(weather_data["humidity"])) \
                .tag("source", "external_api") \
                .time(weather_data["timestamp"], write_precision="ms")
            
            self.write_api.write(bucket=self.bucket, record=point)
            print(f"API weather data stored: {weather_data['temperature']}°C at {weather_data['timestamp']}")
        except Exception as e:
            print(f"Error storing API weather data: {e}")
            
    def query_api_weather_data(self, measure_every_seconds):
        """
        Query recent weather API data.
        
        Args:
            lookback_seconds (int): How far back to query data in seconds
            
        Returns:
            DataFrame: Recent weather API data
        """
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: -3h)
            |> filter(fn: (r) => (r["_measurement"] == "weather_api_data" and r["_field"] == "temperature") or (r["_measurement"] == "temperature" and  r["_field"] == "value" and r["location"] != "indoor"))
            |> aggregateWindow(every: {measure_every_seconds}s, fn: mean, createEmpty: false)
            |> yield(name: "mean")
            |> pivot(rowKey:["_time"], columnKey: ["_measurement"], valueColumn: "_value")
        '''
        
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
        
        result = self.query_api.query_data_frame(query)
        if result.empty:
            return None
        return result
