import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configurations
INFLUXDB_CONFIG = {
    # "url": "http://localhost:8086",
    "url": "https://eu-central-1-1.aws.cloud2.influxdata.com",
    "token": os.getenv("INFLUXDB_TOKEN"),  # Get from environment variable
    "org": "ProgettoIot",
    "bucket": "ProgettoIot"
}

# Analysis configurations
ANALYSIS_CONFIG = {
    "threshold": 1.0,  # Differenza di temperatura per considerare uno spreco
    "measure_every_seconds": 30,
    "forecast_horizon": 60 # 30 minuti
}

WEATHER_API_CONFIG = {
    "api_key": os.getenv("WEATHER_API_KEY"),  # Get from environment variable
    "city": "Bologna",
    "country_code": "IT",
    "units": "metric"  # metric for Celsius
}

# Validate that required environment variables are set
if not INFLUXDB_CONFIG["token"]:
    raise ValueError("INFLUXDB_TOKEN environment variable is not set")

if not WEATHER_API_CONFIG["api_key"]:
    raise ValueError("WEATHER_API_KEY environment variable is not set")


