import os
import json
from pathlib import Path
from typing import Dict, Any

from app.adapters.nps_adapter import parse_nps_park, parse_nps_alerts, parse_nps_events
from app.adapters.weather_adapter import parse_weather_data
from app.adapters.alltrails_adapter import parse_trail_data
# from app.adapters.external_adapter import parse_amenity_place (If you have amenity samples)

# CONFIG
DATA_ROOT = Path("data_samples/nps")
FIRE_ROOT = Path("data_samples/firecrawl") # Adjust if your folder name differs
PARK_CODES = ["YOSE", "ZION", "GRCA"]

def load_json(path: Path) -> Any:
    if not path.exists():
        print(f"⚠️ Missing: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def verify_park_data(folder_name: str):
    print(f"\n--- Verifying {folder_name} ---")
    park_dir = DATA_ROOT / folder_name
    park_code_lower = folder_name.lower()

    # 1. Park Context
    search_data = load_json(park_dir / "parks_search.json")
    if search_data and "data" in search_data and search_data["data"]:
        # Usually the first result is the right one
        park_obj = parse_nps_park(search_data["data"][0])
        print(f"✅ ParkContext: {park_obj.fullName} (Lat: {park_obj.location.lat})")
    else:
        print("❌ ParkContext: Failed to load")

    # 2. Alerts
    alerts_data = load_json(park_dir / "alerts.json")
    if alerts_data:
        alerts = parse_nps_alerts(alerts_data)
        print(f"✅ Alerts: Loaded {len(alerts)} alerts")
    
    # 3. Events
    events_data = load_json(park_dir / "events.json")
    if events_data:
        events = parse_nps_events(events_data)
        print(f"✅ Events: Loaded {len(events)} events")

    # 4. Weather
    weather_data = load_json(park_dir / "weather.json")
    if weather_data:
        weather = parse_weather_data(weather_data, park_code_lower)
        print(f"✅ Weather: {weather.current_condition}, {weather.current_temp_f}°F")

def verify_trail_scrapes():
    print(f"\n--- Verifying Trail Scrapes ---")
    # Assuming you have scraped_extract_llm.json in a specific folder
    # Adjust path to where you actually saved the trail data
    trail_path = FIRE_ROOT / "scraped_extract_llm.json" 
    
    # If the file isn't there, we just skip (since you might not have scraped all yet)
    if not trail_path.exists():
        # check current directory as fallback (based on previous attachments)
        trail_path = Path("scraped_extract_llm.json")

    if trail_path.exists():
        data = load_json(trail_path)
        trail = parse_trail_data(data, "test_park")
        print(f"✅ Trail: {trail.name} ({trail.difficulty}) - {len(trail.recent_reviews)} reviews")
    else:
        print(f"⚠️ No trail scrape found at {trail_path}")

def main():
    print("🚀 STARTING PHASE 1 VERIFICATION 🚀")
    
    # Verify NPS & Weather Data
    for code in PARK_CODES:
        if (DATA_ROOT / code).exists():
            verify_park_data(code)
        else:
            print(f"\n⚠️ Skipping {code}: Directory not found")

    # Verify AllTrails Data
    verify_trail_scrapes()

    print("\n🎉 PHASE 1 COMPLETE")

if __name__ == "__main__":
    main()
