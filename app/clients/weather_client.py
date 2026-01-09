import os
import logging
from typing import Optional, List, Dict

from app.clients.base_client import BaseClient
from app.models import WeatherSummary, ZonalForecast
from app.adapters.weather_adapter import parse_weather_data, estimate_temp_at_elevation

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
            logger.info(f"Fetching weather for {park_code} at {params['q']}")
            with open("debug_api_calls.log", "a") as f:
                f.write(f"Request: {params['q']}\n")
                
            data = self._get("forecast.json", params=params)
            # Use the adapter to parse
            return parse_weather_data(data, park_code)
            
        except Exception as e:
            logger.error(f"Failed to fetch weather for {park_code}: {e}")
            return None

    def get_zonal_forecasts(
        self, 
        park_code: str, 
        zones: List[Dict],
        base_zone_name: str,
        days: int = 3
    ) -> Dict[str, ZonalForecast]:
        """
        Fetch weather for all zones in a park.
        
        Args:
            park_code: Park code
            zones: List of zone configs with name, lat, lon, elevation_ft
            base_zone_name: Name of the base zone for delta calculations
            days: Number of forecast days
        
        Returns:
            Dict mapping zone_name -> ZonalForecast
        """
        results = {}
        base_temp = None
        base_elev = None
        
        # Get base elevation
        for z in zones:
            if z["name"] == base_zone_name:
                base_elev = z["elevation_ft"]
                break
        
        for zone in zones:
            weather = self.get_forecast(park_code, zone["lat"], zone["lon"], days)
            if weather:
                # Store base zone temp for delta calculations
                if zone["name"] == base_zone_name:
                    base_temp = weather.current_temp_f
                
                results[zone["name"]] = ZonalForecast(
                    zone_name=zone["name"],
                    elevation_ft=zone["elevation_ft"],
                    current_temp_f=weather.current_temp_f,
                    current_condition=weather.current_condition,
                    wind_mph=weather.wind_mph,
                    humidity=weather.humidity,
                    forecast=weather.forecast,
                    delta_from_base=None  # Will be set after all zones fetched
                )
        
        # Calculate deltas and apply lapse rate fix if necessary
        if base_temp is not None:
            for zone_name, forecast in results.items():
                if zone_name != base_zone_name:
                    # Fix for API returning identical data for nearby zones
                    # If temp is effectively identical to base but elevation difference is significant (> 500ft),
                    # overwrite API temp with lapse rate calculation.
                    if base_elev is not None and abs(forecast.current_temp_f - base_temp) < 1.0 and abs(forecast.elevation_ft - base_elev) > 500:
                         logger.warning(f"Zone {zone_name} temp ({forecast.current_temp_f}) too similar to base. Using lapse rate.")
                         new_temp = estimate_temp_at_elevation(base_temp, base_elev, forecast.elevation_ft)
                         forecast.current_temp_f = round(new_temp, 1)

                    forecast.delta_from_base = round(forecast.current_temp_f - base_temp, 1)
        
        logger.info(f"Fetched zonal weather for {park_code}: {list(results.keys())}")
        return results
