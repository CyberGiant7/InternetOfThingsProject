from influxdb_client import InfluxDBClient
import pandas as pd
from datetime import timedelta
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
        df['_time'] = pd.to_datetime(df['_time']) + timedelta(hours=1)
        df.set_index('_time', inplace=True)
        df = df.asfreq(f'{measure_every_seconds}s')
        return df