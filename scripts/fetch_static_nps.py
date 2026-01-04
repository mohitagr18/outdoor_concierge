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
    Splits raw NPS places data into 'trails' (candidates) and 'things' based on broad recall logic.
    Stage 1: Broad Recall - separate likely hike candidates from obvious infrastructure.
    """
    items = places_raw_data.get("data", [])
    
    # Positive Signals: implies hiking context
    HIKE_KEYWORDS = [
        "trail", "trailhead", "hike", "hiking", "route", "walk", "loop", "path", 
        "canyon", "rim", "overlook", "point", "junction", "narrows", "landing", 
        "bridge", "mesa", "wash", "access"
    ]
    
    # Negative Signals: implies non-hike infrastructure
    INFRASTRUCTURE_KEYWORDS = [
        "visitor center", "museum", "gift shop", "campground", "lodging", 
        "picnic", "restroom", "amphitheater", "station", "office", "entrance", 
        "exhibit", "wayside", "marker", "shuttle stop", "bus stop", "parking",
        "residence", "village", "hotel", "store", "school", "church"
    ]

    # Content Signals: words in description that strongly suggest a hike description
    CONTENT_INDICATORS = ["miles", "km", "elevation", "round-trip", "strenuous", "moderate", "easy", "climb", "hike"]

    def contains_whole_word(text, keyword):
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        return bool(re.search(pattern, text.lower()))

    trails_candidates = []
    things = []
    
    for item in items:
        title = item.get("title", "")
        # Unified Description: Handle schema differences between Places (listingDescription) and ThingsToDo (longDescription)
        desc_parts = [
            item.get("listingDescription") or "",
            item.get("bodyText") or "",
            item.get("shortDescription") or "",
            item.get("longDescription") or ""
        ]
        desc = " ".join(desc_parts)
        title_lower = title.lower()
        desc_lower = desc.lower()

        # 1. Check Negative Signals first (fast reject)
        is_infrastructure = any(contains_whole_word(title_lower, kw) for kw in INFRASTRUCTURE_KEYWORDS)
        
        # 2. Check Positive Signals
        has_hike_keyword = any(contains_whole_word(title_lower, kw) for kw in HIKE_KEYWORDS)
        
        # 3. Content Rescue: Even if it looks like infrastructure (e.g. "Glacier Point"), 
        # is it actually describing a hike starting there?
        has_content_indicators = sum(1 for w in CONTENT_INDICATORS if w in desc_lower) >= 2

        # LOGIC:
        is_trail = False
        
        if is_infrastructure:
            # If it's explicitly named "Visitor Center", it's a thing. 
            # Unless it's "Visitor Center Trailhead" - but usually "Visitor Center" is the building.
            # We'll be strict on infrastructure words in title.
             is_trail = False
        elif has_hike_keyword:
             is_trail = True
        elif has_content_indicators:
             # Even if title is generic, if description talks about miles and elevation, it's a trail candidate
             is_trail = True
             
        # Ambiguity Handling: "Overlook" or "Point"
        if contains_whole_word(title_lower, "overlook") or contains_whole_word(title_lower, "point"):
             # Relaxed Rule: If description says "trail" or "hike", keep it.
             # Or if it has at least 1 content indicator (miles, moderate, etc)
             is_hike_desc = "trail" in desc_lower or "hike" in desc_lower
             if not has_content_indicators and not is_hike_desc:
                 is_trail = False

        if is_trail:
            trails_candidates.append(item)
        else:
            things.append(item)
            
    return {"data": trails_candidates, "total": str(len(trails_candidates))}, \
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
            
            # Parsed (UI Fixture)
            parsed = method(park_code, limit=limit)
            save_json(parsed, park_code, filename)
            
            return raw # Return raw data for combination

        fetch_and_save("campgrounds", nps.get_campgrounds, "campgrounds.json")
        fetch_and_save("visitorcenters", nps.get_visitor_centers, "visitor_centers.json")
        fetch_and_save("alerts", nps.get_alerts, "alerts.json")
        fetch_and_save("events", nps.get_events, "events.json")
        fetch_and_save("webcams", nps.get_webcams, "webcams.json")
        
        # --- MERGED PLACES & THINGS TO DO ---
        places_raw = fetch_and_save("places", nps.get_places, "places.json")
        things_raw = fetch_and_save("thingstodo", nps.get_things_to_do, "things_to_do.json")
        
        # Combine items from both endpoints
        combined_items = {}
        for item in places_raw.get("data", []):
            combined_items[item["id"]] = item
        for item in things_raw.get("data", []):
            combined_items[item["id"]] = item
            
        merged_data = {"data": list(combined_items.values())}
        
        # Run classification on the SUPER SET
        trails_raw, things_classified_raw = classify_places(merged_data)
        save_json(trails_raw, park_code, "raw_trails.json", is_raw=True)
        save_json(things_classified_raw, park_code, "raw_things.json", is_raw=True)
        
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
