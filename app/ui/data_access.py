import logging
import streamlit as st
from typing import Optional, Dict, List, Any
from datetime import datetime

from app.services.data_manager import DataManager
from app.models import (
    ParkContext, Campground, VisitorCenter, Webcam, 
    Place, ThingToDo, PassportStamp, Alert, Event, 
    WeatherSummary, Amenity, PhotoSpot, ScenicDrive
)

logger = logging.getLogger(__name__)
data_manager = DataManager()

def get_park_static_data(park_code: str, nps_client=None) -> Dict[str, Any]:
    """
    Loads all static fixture data for a park from disk.
    If park_details.json doesn't exist and nps_client is provided, fetches from NPS API.
    """
    result = {
        "park_details": None, "campgrounds": [], "visitor_centers": [],
        "webcams": [], "places": [], "things_to_do": [],
        "passport_stamps": [], "trails": [], "photo_spots": [],
        "scenic_drives": [], "amenities": {}
    }
    
    # Generic loader helper
    def load_list(filename, model_class, key):
        raw = data_manager.load_fixture(park_code, filename)
        if raw:
            try:
                # Handle list vs dict wrapper (just in case)
                items = raw if isinstance(raw, list) else raw.get(key, raw.get("data", []))
                result[key] = [model_class(**item) for item in items]
            except Exception as e:
                logger.error(f"Failed to parse {key} for {park_code}: {e}")
                # Add to errors for debug UI
                result["_errors"] = result.get("_errors", []) + [f"{key} parse error: {e}"]

    # Load park details - try fixture first, then API fallback
    park_raw = data_manager.load_fixture(park_code, "park_details.json")
    if park_raw:
        try:
            result["park_details"] = ParkContext(**park_raw)
        except Exception as e:
            logger.error(f"Failed to parse park_details: {e}")
    elif nps_client:
        # No local fixture - fetch from NPS API
        logger.info(f"No park_details fixture for {park_code}, fetching from NPS API...")
        try:
            park_context = nps_client.get_park_details(park_code)
            if park_context:
                result["park_details"] = park_context
                logger.info(f"Fetched park details for {park_code} from API")
        except Exception as e:
            logger.error(f"Failed to fetch park_details from API: {e}")

    load_list("campgrounds.json", Campground, "campgrounds")
    load_list("visitor_centers.json", VisitorCenter, "visitor_centers")
    load_list("webcams.json", Webcam, "webcams")
    load_list("places.json", Place, "places")
    load_list("things_to_do.json", ThingToDo, "things_to_do")
    load_list("passport_stamps.json", PassportStamp, "passport_stamps")
    # Trails v2 is a list of dicts/TrailSummary
    load_list("trails_v2.json", dict, "trails") 
    # Photo Spots (Now expects valid model structure from your fixed script)
    load_list("photo_spots.json", PhotoSpot, "photo_spots")
    # Scenic Drives
    load_list("scenic_drives.json", ScenicDrive, "scenic_drives")

    return result

def get_volatile_data(park_code: str, orchestrator) -> Dict[str, Any]:
    """
    Loads volatile data (weather, alerts, events) using daily disk cache.
    Falls back to API fetch if cache miss, then saves to disk for the day.
    """
    if not orchestrator:
        return {"weather": None, "zone_weather": None, "alerts": [], "events": []}
    
    result = {"weather": None, "zone_weather": None, "alerts": [], "events": []}
    
    # Get static data for park location and zone config
    park_data = get_park_static_data(park_code, nps_client=orchestrator.nps if hasattr(orchestrator, 'nps') else None)
    pd = park_data.get("park_details")
    
    # Check for zone config in park_details.json (raw fixture)
    raw_park_details = data_manager.load_fixture(park_code, "park_details.json") or {}
    weather_zones = raw_park_details.get("weather_zones", [])
    base_zone_name = raw_park_details.get("base_weather_zone")
    
    
    # --- Zonal Weather (if zones defined) ---
    if weather_zones and base_zone_name:
        zone_weather = data_manager.load_daily_cache(park_code, "zone_weather")
        if zone_weather:
            result["zone_weather"] = zone_weather
        else:
            # Fetch weather for all zones
            try:
                # Instantiate fresh client to bypass cached orchestrator instance
                from app.clients.weather_client import WeatherClient
                wc = WeatherClient() 
                zone_data = wc.get_zonal_forecasts(
                    park_code, weather_zones, base_zone_name
                )
                if zone_data:
                    # Serialize ZonalForecast objects for caching
                    cache_data = {}
                    for zone_name, forecast in zone_data.items():
                        if hasattr(forecast, 'model_dump'):
                            cache_data[zone_name] = forecast.model_dump()
                        else:
                            cache_data[zone_name] = forecast
                    
                    result["zone_weather"] = cache_data
                    data_manager.save_daily_cache(park_code, "zone_weather", cache_data)
                    logger.info(f"Fetched zonal weather for {park_code}: {list(zone_data.keys())}")
            except Exception as e:
                logger.error(f"Zonal weather fetch failed for {park_code}: {e}")
    
    # --- Regular Weather (fallback or if no zones) ---
    weather = data_manager.load_daily_cache(park_code, "weather")
    if weather:
        result["weather"] = weather
    elif pd and pd.location:
        try:
            w = orchestrator.weather.get_forecast(park_code, pd.location.lat, pd.location.lon)
            result["weather"] = w
            # Save to daily cache (will serialize Pydantic model if needed)
            data_manager.save_daily_cache(park_code, "weather", w.model_dump() if hasattr(w, 'model_dump') else w)
        except Exception as e:
            logger.error(f"Weather fetch failed: {e}")

    # --- Alerts ---
    alerts = data_manager.load_daily_cache(park_code, "alerts")
    if alerts:
        # Convert cached dicts to Alert objects
        from app.models import Alert as AlertModel
        try:
            result["alerts"] = [AlertModel(**a) if isinstance(a, dict) else a for a in alerts]
        except Exception as parse_err:
            logger.warning(f"Failed to parse cached alerts: {parse_err}")
            result["alerts"] = alerts  # Fallback to raw dicts
    else:
        try:
            a = orchestrator.nps.get_alerts(park_code)
            result["alerts"] = a
            # Serialize list of Pydantic models
            data_manager.save_daily_cache(park_code, "alerts", [item.model_dump() if hasattr(item, 'model_dump') else item for item in a])
        except Exception as e:
            logger.error(f"Alerts fetch failed: {e}")

    # --- Events ---
    events = data_manager.load_daily_cache(park_code, "events")
    if events:
        # Convert cached dicts to Event objects
        from app.models import Event as EventModel
        try:
            result["events"] = [EventModel(**e) if isinstance(e, dict) else e for e in events]
        except Exception as parse_err:
            logger.warning(f"Failed to parse cached events: {parse_err}")
            result["events"] = events  # Fallback to raw dicts
    else:
        try:
            e = orchestrator.nps.get_events(park_code)
            result["events"] = e
            # Serialize list of Pydantic models
            data_manager.save_daily_cache(park_code, "events", [item.model_dump() if hasattr(item, 'model_dump') else item for item in e])
        except Exception as e:
            logger.error(f"Events fetch failed: {e}")
        
    return result

def clear_volatile_cache():
    """
    Clears daily cache for today for all parks.
    This forces a re-fetch from APIs on next load.
    """
    import os
    import shutil
    from datetime import datetime
    
    today = datetime.now().strftime("%Y-%m-%d")
    cache_root = "data_cache"
    
    if os.path.exists(cache_root):
        for park_dir in os.listdir(cache_root):
            today_cache = os.path.join(cache_root, park_dir, today)
            if os.path.exists(today_cache):
                try:
                    shutil.rmtree(today_cache)
                    logger.info(f"Cleared daily cache: {today_cache}")
                except Exception as e:
                    logger.error(f"Failed to clear cache {today_cache}: {e}")

