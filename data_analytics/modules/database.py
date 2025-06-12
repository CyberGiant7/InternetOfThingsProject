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

    def query_temperature_data(self, measure_every_seconds):
        query = f'''
        from(bucket: "{INFLUXDB_CONFIG["bucket"]}")
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
        
        self.write_api.write(bucket=INFLUXDB_CONFIG["bucket"], record=point)

    def log_alarm_event(self, indoor_temp, predicted_temp):
        point = Point("temperature_alarms") \
            .field("indoor_temperature", indoor_temp) \
            .field("predicted_temperature", predicted_temp) \
            .field("temperature_difference", abs(predicted_temp - indoor_temp))
        
        self.write_api.write(bucket=INFLUXDB_CONFIG["bucket"], record=point)
    