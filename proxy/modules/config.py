import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MQTT Configuration
MQTT_BROKER = "localhost" # Alternative broker
# MQTT_BROKER = "192.168.137.155"  
MQTT_PORT = 1883
CLIENT_ID = "DataProxyClient"
USER = "arduino"
PASSWORD = "progettoiot"

# InfluxDB Configuration
# INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_URL = "https://eu-central-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")  # Get from environment variable
INFLUXDB_ORG = "ProgettoIot"
INFLUXDB_BUCKET = "ProgettoIot"

# Predefined commands
COMMANDS = {
    "Turn On HVAC": {"topic": "hvac/control", "message": "start"},
    "Turn Off HVAC": {"topic": "hvac/control", "message": "stop"},
    "Turn On LED": {"topic": "hvac/led", "message": "on"},
    "Turn Off LED": {"topic": "hvac/led", "message": "off"},
}
