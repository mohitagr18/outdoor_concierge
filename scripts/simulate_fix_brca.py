import sys
import os
import json
import logging

# Setup basic logging to stdout
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, '.')

from scripts.fetch_static_nps import classify_places

def simulate_fetch_and_classify_trails(park_code: str):
    park_code = park_code.upper()
    
    # -------------------------------------------------------------
    # PROPOSED FIX: Read from RAW data, not FIXTURES
    # -------------------------------------------------------------
    raw_dir = f"data_samples/nps/raw/{park_code}"
    
    places_path = f"{raw_dir}/places.json"
    things_path = f"{raw_dir}/thingstodo.json"
    
    if not os.path.exists(places_path) or not os.path.exists(things_path):
        logger.error(f"❌ Missing raw data. Places: {os.path.exists(places_path)}, Things: {os.path.exists(things_path)}")
        return

    logger.info(f"📂 Reading RAW places from: {places_path}")
    with open(places_path, 'r') as f:
        places_raw = json.load(f)
        # Handle list vs dict (places.json from API is usually a list or dict with 'data')
        # Based on fetcher logic, we expect list of dicts or similar structure
        if isinstance(places_raw, dict) and 'data' in places_raw:
             places_raw = places_raw['data']
    
    logger.info(f"📂 Reading RAW things_to_do from: {things_path}")
    with open(things_path, 'r') as f:
        things_raw = json.load(f)
        if isinstance(things_raw, dict) and 'data' in things_raw:
             things_raw = things_raw['data']

    # Combine items (logic from ParkDataFetcher)
    combined_items = {}
    for item in (places_raw or []):
        if isinstance(item, dict):
            combined_items[item.get("id", str(len(combined_items)))] = item
    for item in (things_raw or []):
        if isinstance(item, dict):
            combined_items[item.get("id", str(len(combined_items)))] = item
    
    merged_data = {"data": list(combined_items.values())}
    logger.info(f"📊 Total raw items to classify: {len(merged_data['data'])}")
    
    # Run classification
    trails_raw, things_raw_classified = classify_places(merged_data)
    
    trail_count = len(trails_raw.get('data', []))
    logger.info(f"✅ FOUND TRAIL CANDIDATES: {trail_count}")
    
    # Peek at first few
    if trail_count > 0:
        logger.info("First 5 trails found:")
        for t in trails_raw['data'][:5]:
            logger.info(f"  - {t.get('title')}")

if __name__ == "__main__":
    simulate_fetch_and_classify_trails("LAVO")
