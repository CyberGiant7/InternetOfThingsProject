from influxdb_client import InfluxDBClient, Point
from datetime import datetime
from modules.config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET

class InfluxDBManager:
    def __init__(self):
        self.client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        self.write_api = self.client.write_api()
        self.query_api = self.client.query_api()
        
    def write_sensor_data(self, data, device_timestamp=None):
        """Write sensor data to InfluxDB"""
        try:
            if device_timestamp:
                # Compute latency
                latency = datetime.now() - device_timestamp
                # Write latency to InfluxDB
                self.write_api.write(
                    bucket=INFLUXDB_BUCKET,
                    record=[
                        Point("latency").field("value", latency.microseconds / 1000)
                    ]
                )
            
            # Write temperature and humidity data
            for location, temp, hum in [("indoor", data.tempIndoor, data.humIndoor),
                                     ("outdoor", data.tempOutdoor, data.humOutdoor)]:
                self.write_api.write(
                    bucket=INFLUXDB_BUCKET,
                    record=[
                        Point("temperature").tag("location", location).field("value", temp),
                        Point("humidity").tag("location", location).field("value", hum)
                    ]
                )
            return True
        except Exception as e:
            print(f"Error writing to InfluxDB: {str(e)}")
            return False
            
    def check_recent_alarms(self):
        """Check if there are any temperature alarms in the last 10 seconds"""
        try:
            alarms = self.query_api.query(f'''
                from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: -10s)
                |> filter(fn: (r) => r._measurement == "temperature_alarms")
            ''')
            
            return len(list(alarms)) > 0
        except Exception as e:
            print(f"Error checking alarms: {str(e)}")
            return False
