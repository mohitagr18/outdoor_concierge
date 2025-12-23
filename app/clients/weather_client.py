import os
import logging
from typing import Optional

from app.clients.base_client import BaseClient
from app.models import WeatherSummary
from app.adapters.weather_adapter import parse_weather_data

logger = logging.getLogger(__name__)

class WeatherClient(BaseClient):
    """
    Client for WeatherAPI.com.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("WEATHER_API_KEY")
        if not self.api_key:
            raise ValueError("WEATHER_API_KEY is not set.")
            
        super().__init__(base_url="http://api.weatherapi.com/v1")

    def get_forecast(self, park_code: str, lat: float, lon: float, days: int = 3) -> Optional[WeatherSummary]:
        """
        Fetch weather forecast for a park's location.
        """
        params = {
            "key": self.api_key,
            "q": f"{lat},{lon}",
            "days": days,
            "aqi": "no",
            "alerts": "yes"
        }
        
        try:
            data = self._get("forecast.json", params=params)
            # Use the adapter to parse
            return parse_weather_data(data, park_code)
            
        except Exception as e:
            logger.error(f"Failed to fetch weather for {park_code}: {e}")
            return None
