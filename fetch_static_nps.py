import os
import json
import logging
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

try:
    from dotenv import load_dotenv
    from app.clients.nps_client import NPSClient
    # ExternalClient removed - handled by admin_fetch_amenities.py
except ImportError as e:
    print(f"CRITICAL: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SeedFixtures")

load_dotenv()

TARGET_PARKS = ["YOSE", "ZION", "GRCA"]
OUTPUT_DIR = "data_samples/ui_fixtures"
ALLTRAILS_SOURCE = os.path.join("data_samples", "firecrawl", "scraped_extract_llm.json")

def save_json(data, park_code, filename):
    """
    Saves data to data_samples/ui_fixtures/{PARK_CODE}/{filename}.
    Handles Pydantic models automatically.
    """
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

    if not nps_key:
        logger.error("Missing NPS_API_KEY in .env")
        return

    nps = NPSClient(api_key=nps_key)

    # 1. Prepare AllTrails Fixture (Load once, use for all)
    trails_fixture = []
    if os.path.exists(ALLTRAILS_SOURCE):
        try:
            with open(ALLTRAILS_SOURCE, "r") as f:
                single_trail = json.load(f)
                trails_fixture = [single_trail] if isinstance(single_trail, dict) else single_trail
            logger.info("Loaded AllTrails mock data.")
        except Exception as e:
            logger.error(f"Error loading AllTrails source: {e}")

    for park_code in TARGET_PARKS:
        logger.info(f"================ {park_code} ================")
        
        # --- NPS Data Points (Static/Frozen) ---
        logger.info(f"Fetching NPS Static Data for {park_code}...")
        
        # Park Details
        park = nps.get_park_details(park_code)
        save_json(park, park_code, "park_details.json")
        
        # Campgrounds (Adapter now ensures 'amenities' are included)
        save_json(nps.get_campgrounds(park_code), park_code, "campgrounds.json")

        # Visitor Centers
        save_json(nps.get_visitor_centers(park_code), park_code, "visitor_centers.json")

        # Alerts
        save_json(nps.get_alerts(park_code), park_code, "alerts.json")

        # Events
        save_json(nps.get_events(park_code), park_code, "events.json")
        
        # Webcams
        save_json(nps.get_webcams(park_code), park_code, "webcams.json")
        
        # Places (Adapter now removes 'tags' and ensures 'amenities')
        save_json(nps.get_places(park_code), park_code, "places.json")
        
        # Things To Do
        save_json(nps.get_things_to_do(park_code), park_code, "things_to_do.json")
        
        # Passport Stamps
        if hasattr(nps, "get_passport_stamps"):
            try:
                save_json(nps.get_passport_stamps(park_code), park_code, "passport_stamps.json")
            except Exception as e:
                logger.warning(f"Passport fetch failed: {e}")

        # --- Trails (From Firecrawl Mock) ---
        if trails_fixture:
             save_json(trails_fixture, park_code, "trails.json")

        logger.info("✅ Data Capture Complete.")

if __name__ == "__main__":
    main()
