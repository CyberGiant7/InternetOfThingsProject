import requests
import time
import random
from datetime import datetime
import math
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Proxy endpoint
PROXY_URL = "http://localhost:8080/sensor-data"

# Configure retry strategy
retry_strategy = Retry(
    total=3,  # number of retries
    backoff_factor=1,  # wait 1, 2, 4 seconds between retries
    status_forcelist=[500, 502, 503, 504]  # HTTP status codes to retry on
)
session = requests.Session()
session.mount("http://", HTTPAdapter(max_retries=retry_strategy))

def generate_sine_wave(time_step, amplitude, period, phase, base_value):
    """Generate a sine wave value for smooth temperature variations."""
    return amplitude * math.sin(2 * math.pi * time_step / period + phase) + base_value

def generate_sensor_data():
    """Generate realistic sensor data with some variations."""
    current_time = datetime.now().isoformat()
    time_step = time.time()

    # Generate indoor temperature (20-25°C with smooth variations)
    temp_indoor = generate_sine_wave(
        time_step=time_step,
        amplitude=2.5,
        period=3600,  # 1-hour period
        phase=0,
        base_value=22.5
    )

    # Generate outdoor temperature (15-30°C with smooth variations)
    temp_outdoor = generate_sine_wave(
        time_step=time_step,
        amplitude=7.5,
        period=86400,  # 24-hour period
        phase=0,
        base_value=22.5
    )

    # Generate humidity (40-60% with random variations)
    hum_indoor = random.uniform(40, 60)
    hum_outdoor = random.uniform(30, 70)

    return {
        "tempIndoor": round(temp_indoor, 2),
        "humIndoor": round(hum_indoor, 2),
        "tempOutdoor": round(temp_outdoor, 2),
        "humOutdoor": round(hum_outdoor, 2),
        "timestamp": current_time
    }

def main():
    print("Starting data generation...")
    print(f"Attempting to connect to proxy at {PROXY_URL}")
    
    retry_count = 0
    max_retries = 5  # Maximum number of initial connection attempts

    while True:
        try:
            data = generate_sensor_data()
            response = session.post(PROXY_URL, json=data, timeout=5)
            
            if response.status_code == 200:
                print(f"Data sent successfully: {data}")
                print(f"Response: {response.json()}")
                retry_count = 0  # Reset retry count on successful connection
            else:
                print(f"Error sending data: {response.status_code}")
                print(f"Response: {response.text}")

        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count <= max_retries:
                print(f"\nConnection attempt {retry_count}/{max_retries} failed.")
                print("Make sure the proxy server (FastAPI application) is running at", PROXY_URL)
                print(f"Error details: {str(e)}")
                print(f"Retrying in 10 seconds...\n")
                time.sleep(10)
                continue
            else:
                print(f"\nFailed to connect after {max_retries} attempts.")
                print("Please:")
                print("1. Ensure the proxy server is running (python data_proxy.py)")
                print("2. Verify the server address is correct:", PROXY_URL)
                print("3. Check if port 8080 is available and not blocked")
                print("\nRetrying in 30 seconds...\n")
                retry_count = 0  # Reset retry count and continue trying
                
        time.sleep(5)

if __name__ == "__main__":
    main()