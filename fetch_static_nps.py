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
RAW_DATA_DIR = "data_samples/nps/raw"
ALLTRAILS_SOURCE = os.path.join("data_samples", "firecrawl", "scraped_extract_llm.json")

def save_json(data, park_code, filename, is_raw=False):
    """
    Saves data to data_samples/ui_fixtures/{PARK_CODE}/{filename} 
    or data_samples/nps/raw/{PARK_CODE}/{filename} if is_raw is True.
    """
    base = RAW_DATA_DIR if is_raw else OUTPUT_DIR
    path = os.path.join(base, park_code)
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

import re

def classify_places(places_raw_data):
    """
    Splits raw NPS places data into 'trails' and 'things' based on keywords.
    Refined to avoid false positives like ski areas and sub-word matches (e.g., 'always').
    """
    items = places_raw_data.get("data", [])
    
    # These strongly imply a trail
    TRAIL_KEYWORDS = ["Trail", "Loop", "Hike", "Hiking", "Trailhead", "Route", "Pass", "Way", "Path", "Nature Walk"]
    
    # These strongly imply a non-trail landmark or structure
    NON_TRAIL_KEYWORDS = [
        "Cabin", "Office", "Entrance", "Museum", "Gallery", "Station", 
        "Building", "Center", "Residence", "Lodge", "Village", "Church", 
        "School", "Store", "House", "Studio", "Hotel", "Restaurant",
        "Ski", "Area", "Point", "Overlook", "View", "Vista", "Grove", 
        "Meadow", "Beach", "Rock", "Bridge", "Dam", "Road", "Campground",
        "Picnic", "Theater", "Stables", "Amphitheater", "Peak", "Dome", "Mountain",
        "Hut", "Cottage", "Tower", "Lighthouse", "Monument"
    ]
    
    def contains_whole_word(text, keyword):
        # Use regex to find whole words, avoiding matches like 'always' for 'way'
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        return bool(re.search(pattern, text.lower()))

    trails = []
    things = []
    
    for item in items:
        title = item.get("title", "")
        desc = (item.get("listingDescription") or "").lower()
        title_lower = title.lower()
        
        # 1. Whole-word checks
        is_structure_or_landmark = any(contains_whole_word(title_lower, kw) for kw in NON_TRAIL_KEYWORDS)
        has_trail_title = any(contains_whole_word(title_lower, kw) for kw in TRAIL_KEYWORDS)
        has_trail_desc = any(contains_whole_word(desc, kw) for kw in TRAIL_KEYWORDS)
        
        # 2. Logic Priority
        if contains_whole_word(title_lower, "trailhead"):
            is_trail = True
        elif is_structure_or_landmark:
            is_trail = False
        elif has_trail_title or has_trail_desc:
            is_trail = True
        else:
            is_trail = False

        if is_trail:
            trails.append(item)
        else:
            things.append(item)
            
    return {"data": trails, "total": str(len(trails))}, \
           {"data": things, "total": str(len(things))}

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
        
        # --- NPS Data Points ---
        
        # 1. Park Details (Raw & UI)
        park_raw = nps._get("parks", params={"parkCode": park_code, "limit": 1}, headers=nps._get_headers())
        save_json(park_raw, park_code, "parks.json", is_raw=True)
        
        from app.adapters.nps_adapter import parse_nps_park
        if park_raw.get("data"):
            park = parse_nps_park(park_raw["data"][0])
            save_json(park, park_code, "park_details.json")

        # helper for fetching and saving both
        def fetch_and_save(endpoint, method, filename, limit=500):
            logger.info(f"Fetching {endpoint} for {park_code}...")
            # Raw
            raw = nps._get(endpoint, params={"parkCode": park_code, "limit": limit}, headers=nps._get_headers())
            save_json(raw, park_code, f"{endpoint}.json", is_raw=True)
            
            # SPECIAL CASE: Classify Places
            if endpoint == "places":
                trails_raw, things_raw = classify_places(raw)
                save_json(trails_raw, park_code, "raw_trails.json", is_raw=True)
                save_json(things_raw, park_code, "raw_things.json", is_raw=True)

            # Parsed (UI Fixture)
            parsed = method(park_code, limit=limit)
            save_json(parsed, park_code, filename)

        fetch_and_save("campgrounds", nps.get_campgrounds, "campgrounds.json")
        fetch_and_save("visitorcenters", nps.get_visitor_centers, "visitor_centers.json")
        fetch_and_save("alerts", nps.get_alerts, "alerts.json")
        fetch_and_save("events", nps.get_events, "events.json")
        fetch_and_save("webcams", nps.get_webcams, "webcams.json")
        fetch_and_save("places", nps.get_places, "places.json")
        fetch_and_save("thingstodo", nps.get_things_to_do, "things_to_do.json")
        
        # Passport Stamps (special case if not in all clients)
        if hasattr(nps, "get_passport_stamps"):
            try:
                fetch_and_save("passportstamplocations", nps.get_passport_stamps, "passport_stamps.json")
            except Exception as e:
                logger.warning(f"Passport fetch failed: {e}")

        # --- Trails (From Firecrawl Mock) ---
        if trails_fixture:
             save_json(trails_fixture, park_code, "trails.json")

        logger.info("✅ Data Capture Complete.")

if __name__ == "__main__":
    main()
