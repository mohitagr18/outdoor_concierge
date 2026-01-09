from typing import Dict, Any, List, Optional
from app.models import WeatherSummary, DailyForecast, ZonalForecast

# Meteorological lapse rate: temperature drops ~3.5°F per 1,000 ft elevation gain
LAPSE_RATE_F_PER_1000FT = 3.5


def estimate_temp_at_elevation(
    base_temp_f: float,
    base_elevation_ft: int,
    target_elevation_ft: int
) -> float:
    """
    Apply lapse rate to estimate temperature at a different elevation.
    
    Args:
        base_temp_f: Temperature at base elevation
        base_elevation_ft: Elevation where base_temp_f was measured
        target_elevation_ft: Elevation where we want to estimate temperature
    
    Returns:
        Estimated temperature at target elevation
    """
    elevation_diff = target_elevation_ft - base_elevation_ft
    temp_adjustment = (elevation_diff / 1000) * LAPSE_RATE_F_PER_1000FT
    return round(base_temp_f - temp_adjustment, 1)


def get_trail_weather(
    zone_weather: Dict[str, ZonalForecast],
    trail_zone: str,
    trail_elevation_ft: Optional[int],
    base_zone_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get weather for a specific trail, adjusting from zone weather if needed.
    
    Args:
        zone_weather: Dict of zone_name -> ZonalForecast
        trail_zone: Name of the zone this trail belongs to
        trail_elevation_ft: Trailhead elevation (for fine-tuning)
        base_zone_name: Name of the base zone for delta calculation
    
    Returns:
        Dict with temp, condition, delta_from_base, zone_name
    """
    if not zone_weather or trail_zone not in zone_weather:
        return None
    
    zone_forecast = zone_weather[trail_zone]
    
    # Start with zone's temperature
    temp = zone_forecast.current_temp_f
    
    # Fine-tune if trail elevation differs from zone elevation
    if trail_elevation_ft and trail_elevation_ft != zone_forecast.elevation_ft:
        temp = estimate_temp_at_elevation(
            zone_forecast.current_temp_f,
            zone_forecast.elevation_ft,
            trail_elevation_ft
        )
    
    # Calculate delta from base zone
    delta_from_base = None
    if base_zone_name and base_zone_name in zone_weather:
        base_temp = zone_weather[base_zone_name].current_temp_f
        delta_from_base = round(temp - base_temp, 1)
    
    return {
        "temp": temp,
        "condition": zone_forecast.current_condition,
        "zone_name": trail_zone,
        "delta_from_base": delta_from_base
    }

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
        wind_mph=current.get("wind_mph", 0.0),
        humidity=current.get("humidity", 0),
        forecast=daily_forecasts,
        sunrise=sunrise,
        sunset=sunset,
        weather_alerts=weather_alerts
    )
