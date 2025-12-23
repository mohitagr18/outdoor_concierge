from typing import Dict, Any, List
from app.models import WeatherSummary, DailyForecast

def parse_weather_data(weather_json: Dict[str, Any], park_code: str) -> WeatherSummary:
    """
    Parses the raw JSON response from WeatherAPI (forecast.json) into a WeatherSummary.
    
    Args:
        weather_json: The full dictionary returned by the WeatherAPI.
        park_code: The park code (e.g., 'yose') to associate with this weather data.
    """
    # 1. Extract Current Conditions
    current = weather_json.get("current", {})
    current_condition_obj = current.get("condition", {})
    
    # 2. Extract Forecast Days
    forecast_root = weather_json.get("forecast", {})
    forecast_days_raw = forecast_root.get("forecastday", [])
    
    daily_forecasts: List[DailyForecast] = []
    sunrise = None
    sunset = None

    for i, day_obj in enumerate(forecast_days_raw):
        # Extract Astro data from the first day only
        if i == 0:
            astro = day_obj.get("astro", {})
            sunrise = astro.get("sunrise")
            sunset = astro.get("sunset")

        day_data = day_obj.get("day", {})
        cond_data = day_data.get("condition", {})
        
        daily_forecasts.append(DailyForecast(
            date=day_obj.get("date", ""),
            maxtemp_f=day_data.get("maxtemp_f", 0.0),
            mintemp_f=day_data.get("mintemp_f", 0.0),
            avgtemp_f=day_data.get("avgtemp_f", 0.0),
            daily_chance_of_rain=day_data.get("daily_chance_of_rain", 0),
            condition=cond_data.get("text", "Unknown"),
            uv=day_data.get("uv", 0.0)
        ))

    # 3. Extract Alerts
    # WeatherAPI returns 'alerts': {'alert': [...]} OR empty list/dict depending on subscription
    alerts_root = weather_json.get("alerts", {})
    # If alerts_root is a dict, look for 'alert' list inside. If it's just a list, use it directly (rare but possible in some API versions)
    raw_alerts = alerts_root.get("alert", []) if isinstance(alerts_root, dict) else []
    
    weather_alerts = []
    for alert in raw_alerts:
        weather_alerts.append({
            "event": alert.get("event", "Unknown Event"),
            "severity": alert.get("severity", "Unknown"),
            "headline": alert.get("headline", ""),
            "effective": alert.get("effective", ""),
            "expires": alert.get("expires", "")
        })

    return WeatherSummary(
        parkCode=park_code,
        current_temp_f=current.get("temp_f", 0.0),
        current_condition=current_condition_obj.get("text", "Unknown"),
        forecast=daily_forecasts,
        sunrise=sunrise,
        sunset=sunset,
        weather_alerts=weather_alerts
    )
