import logging
import streamlit as st
from typing import Optional, Dict, List, Any
from datetime import datetime

from app.services.data_manager import DataManager
from app.models import (
    ParkContext, Campground, VisitorCenter, Webcam, 
    Place, ThingToDo, PassportStamp, Alert, Event, 
    WeatherSummary, Amenity, PhotoSpot
)

logger = logging.getLogger(__name__)
data_manager = DataManager()

def get_park_static_data(park_code: str) -> Dict[str, Any]:
    """
    Loads all static fixture data for a park from disk.
    """
    result = {
        "park_details": None, "campgrounds": [], "visitor_centers": [],
        "webcams": [], "places": [], "things_to_do": [],
        "passport_stamps": [], "trails": [], "photo_spots": [],
        "amenities": {}
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

    # Load entities
    park_raw = data_manager.load_fixture(park_code, "park_details.json")
    if park_raw:
        try:
            result["park_details"] = ParkContext(**park_raw)
        except Exception as e:
            logger.error(f"Failed to parse park_details: {e}")

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

    return result

def get_volatile_data(park_code: str, orchestrator) -> Dict[str, Any]:
    # (Same as previous version)
    if not orchestrator:
        return {"weather": None, "alerts": [], "events": []}
    
    cache_key = park_code
    now = datetime.now().timestamp()
    CACHE_TTL = 300
    
    result = {"weather": None, "alerts": [], "events": []}
    
    # Helper to check cache
    def get_cached(key):
        entry = st.session_state.volatile_cache[key].get(cache_key)
        if entry and (now - entry.get("timestamp", 0)) < CACHE_TTL:
            return entry.get("data")
        return None

    # Weather
    weather = get_cached("weather")
    if weather:
        result["weather"] = weather
    else:
        # Fetch live
        park_data = get_park_static_data(park_code)
        pd = park_data.get("park_details")
        if pd and pd.location:
            try:
                w = orchestrator.weather.get_forecast(park_code, pd.location.lat, pd.location.lon)
                result["weather"] = w
                st.session_state.volatile_cache["weather"][cache_key] = {"data": w, "timestamp": now}
            except Exception as e:
                logger.error(f"Weather fetch failed: {e}")

    # Alerts
    alerts = get_cached("alerts")
    if alerts: result["alerts"] = alerts
    else:
        try:
            a = orchestrator.nps.get_alerts(park_code)
            result["alerts"] = a
            st.session_state.volatile_cache["alerts"][cache_key] = {"data": a, "timestamp": now}
        except Exception: pass

    # Events
    events = get_cached("events")
    if events: result["events"] = events
    else:
        try:
            e = orchestrator.nps.get_events(park_code)
            result["events"] = e
            st.session_state.volatile_cache["events"][cache_key] = {"data": e, "timestamp": now}
        except Exception: pass
        
    return result

def clear_volatile_cache():
    st.session_state.volatile_cache = {"weather": {}, "alerts": {}, "events": {}}
