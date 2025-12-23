from typing import Dict, Any, List
from app.models import WeatherSummary, DailyForecast

def parse_weather_data(weather_json: Dict[str, Any], park_code: str) -> WeatherSummary:
    """
    Parses the raw JSON response from WeatherAPI (forecast.json) into a WeatherSummary.
    Robustly handles 'condition' fields whether they are dicts or strings.
    """
    # 1. Extract Current Conditions
    current = weather_json.get("current", {})
    
    # SAFEGUARD: Check if 'condition' is a dict or string
    raw_condition = current.get("condition")
    if isinstance(raw_condition, dict):
        current_text = raw_condition.get("text", "Unknown")
    elif isinstance(raw_condition, str):
        current_text = raw_condition
    else:
        current_text = "Unknown"
    
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
        
        # SAFEGUARD: Check forecast condition similarly
        day_cond_raw = day_data.get("condition")
        if isinstance(day_cond_raw, dict):
            day_cond_text = day_cond_raw.get("text", "Unknown")
        elif isinstance(day_cond_raw, str):
            day_cond_text = day_cond_raw
        else:
            day_cond_text = "Unknown"
        
        daily_forecasts.append(DailyForecast(
            date=day_obj.get("date", ""),
            maxtemp_f=day_data.get("maxtemp_f", 0.0),
            mintemp_f=day_data.get("mintemp_f", 0.0),
            avgtemp_f=day_data.get("avgtemp_f", 0.0),
            daily_chance_of_rain=day_data.get("daily_chance_of_rain", 0),
            condition=day_cond_text,
            uv=day_data.get("uv", 0.0)
        ))

    # 3. Extract Alerts
    alerts_root = weather_json.get("alerts", {})
    # If alerts_root is a dict, look for 'alert' list inside.
    # If it's just a list (rare), use it directly.
    if isinstance(alerts_root, dict):
        raw_alerts = alerts_root.get("alert", [])
    elif isinstance(alerts_root, list):
        raw_alerts = alerts_root
    else:
        raw_alerts = []
    
    weather_alerts = []
    for alert in raw_alerts:
        # Ensure alert is a dict before accessing
        if isinstance(alert, dict):
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
        current_condition=current_text,
        forecast=daily_forecasts,
        sunrise=sunrise,
        sunset=sunset,
        weather_alerts=weather_alerts
    )
