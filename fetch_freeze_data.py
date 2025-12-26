import os
import json
import logging
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

try:
    from dotenv import load_dotenv
    from app.clients.nps_client import NPSClient
    from app.clients.external_client import ExternalClient
    from app.clients.weather_client import WeatherClient
except ImportError as e:
    print(f"CRITICAL: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DataFreezer")
load_dotenv()

TARGET_PARKS = ["YOSE", "ZION", "GRCA"]
OUTPUT_DIR = "data_samples/ui_fixtures"
ALLTRAILS_SOURCE = os.path.join("data_samples", "firecrawl", "scraped_extract_llm.json")

def save_json(data, park_code, filename):
    path = os.path.join(OUTPUT_DIR, park_code)
    os.makedirs(path, exist_ok=True)
    full_path = os.path.join(path, filename)

    try:
        # Pydantic serialization helper
        if isinstance(data, list):
            serialized = [d.model_dump() if hasattr(d, "model_dump") else d for d in data]
        elif hasattr(data, "model_dump"):
            serialized = data.model_dump()
        else:
            serialized = data

        with open(full_path, "w") as f:
            json.dump(serialized, f, indent=2)
        logger.info(f"Saved {full_path}")
    except Exception as e:
        logger.error(f"Failed to save {filename}: {e}")

def main():
    nps_key = os.getenv("NPS_API_KEY")
    serper_key = os.getenv("SERPER_API_KEY")
    weather_key = os.getenv("WEATHER_API_KEY")

    if not all([nps_key, serper_key, weather_key]):
        logger.error("Missing one or more API Keys in .env")
        return

    nps = NPSClient(api_key=nps_key)
    ext = ExternalClient()
    weather = WeatherClient(api_key=weather_key)

    # 1. Prepare AllTrails Fixture (Load once, use for all)
    trails_fixture = []
    if os.path.exists(ALLTRAILS_SOURCE):
        try:
            with open(ALLTRAILS_SOURCE, "r") as f:
                single_trail = json.load(f)
                # Ensure it's a list for the UI
                trails_fixture = [single_trail] if isinstance(single_trail, dict) else single_trail
            logger.info("Loaded AllTrails mock data.")
        except Exception as e:
            logger.error(f"Error loading AllTrails source: {e}")

    for park_code in TARGET_PARKS:
        logger.info(f"================ {park_code} ================")

        # --- NPS Data Points ---
        logger.info(f"Fetching NPS Core & Children for {park_code}...")
        park = nps.get_park_details(park_code)
        save_json(park, park_code, "park_details.json")

        save_json(nps.get_alerts(park_code), park_code, "alerts.json")
        save_json(nps.get_campgrounds(park_code), park_code, "campgrounds.json")
        save_json(nps.get_visitor_centers(park_code), park_code, "visitor_centers.json")
        save_json(nps.get_webcams(park_code), park_code, "webcams.json")
        save_json(nps.get_places(park_code), park_code, "places.json")
        save_json(nps.get_things_to_do(park_code), park_code, "things_to_do.json")

        if hasattr(nps, "get_passport_stamps"):
            try:
                save_json(nps.get_passport_stamps(park_code), park_code, "passport_stamps.json")
            except Exception as e:
                logger.warning(f"Passport fetch failed: {e}")

        # --- Trails (Mock/Scrape) ---
        if trails_fixture:
            save_json(trails_fixture, park_code, "trails.json")

        # --- Location-Based Data (Weather & Amenities) ---
        if park and park.location:
            lat, lon = park.location.lat, park.location.lon

            # Weather
            logger.info("Fetching Weather...")
            save_json(weather.get_forecast(park_code, lat, lon), park_code, "weather.json")

            # Serper Amenities (Unified Call)
            logger.info("Fetching Amenities (Gas, Food, Medical)...")
            try:
                # We now pass a list of queries to the updated client
                all_amenities = ext.get_amenities(
                    ["gas station", "restaurant", "hospital, urgent care"], 
                    lat, lon
                )
                save_json(all_amenities, park_code, "amenities.json")
            except Exception as e:
                logger.error(f"Serper fetch failed: {e}")
        else:
            logger.warning(f"No location data for {park_code}, skipping Weather/Serper.")

    logger.info("✅ Data Capture Complete. Ready for Step 2.")

if __name__ == "__main__":
    main()