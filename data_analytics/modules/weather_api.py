import requests
import time
from pytz import timezone
from datetime import datetime
import logging

class WeatherAPIClient:
    def __init__(self, api_key=None, city="London", country_code="UK", units="metric"):
        """
        Initialize the weather API client.
        
        Args:
            api_key: Your OpenWeatherMap API key
            city: The city to get weather for
            country_code: The country code
            units: Temperature units (metric for Celsius, imperial for Fahrenheit)
        """
        self.api_key = api_key or "YOUR_API_KEY"  # Replace with your actual API key
        self.city = city
        self.country_code = country_code
        self.units = units
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
        self.logger = logging.getLogger(__name__)
        
    def get_current_weather(self):
        """
        Fetch current weather conditions.
        
        Returns:
            dict: Weather data including temperature or None if the request fails
        """
        try:
            params = {
                "q": f"{self.city},{self.country_code}",
                "appid": self.api_key,
                "units": self.units
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            
            weather_data = response.json()
            # Adjust for timezone italian time zone (UTC+2)
            timestamp = datetime.now(tz=timezone('Europe/Rome'))
            
            # print(f"Weather data fetched at {timestamp}: {weather_data}")
            return {
                "timestamp": timestamp,
                "temperature": weather_data["main"]["temp"],
                "humidity": weather_data["main"]["humidity"],
                "description": weather_data["weather"][0]["description"],
                "source": "weather_api"
            }
        except Exception as e:
            self.logger.error(f"Error fetching weather data: {str(e)}")
            return None