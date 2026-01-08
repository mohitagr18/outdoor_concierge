import os
import json
import logging
import math
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
DATA_DIR = "data_samples/ui_fixtures"
TARGET_PARKS = ["YOSE", "ZION", "GRCA"]

# NEW: Mapping matches your updated admin_fetch_amenities.py TASKS
CATEGORY_MAP = {
    "urgent care OR hospital OR emergency room": "Medical",
    "gas station": "Gas Station",
    "ev charging": "EV Charging",
    "restaurant": "Food",
    "grocery store": "Supplies", # or "Groceries"
    "lodging OR hotel OR motel OR campground": "Lodging"
}

def calculate_haversine(lat1, lon1, lat2, lon2):
    """Calculates distance in miles between two lat/lon points."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 9999.9
    try:
        R = 3958.8  # Earth radius in miles
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(R * c, 2)
    except (ValueError, TypeError):
        return 9999.9

def get_hub_coords(park_code: str, hub_name_query: str) -> tuple:
    """Finds lat/lon for a named hub (VC/Entrance) in the park's static data."""
    park_dir = os.path.join(DATA_DIR, park_code)
    source_files = ["visitor_centers.json", "places.json"]
    
    hub_query_clean = hub_name_query.lower().replace(" ", "").replace("_", "")
    
    for fname in source_files:
        fpath = os.path.join(park_dir, fname)
        if not os.path.exists(fpath):
            continue
            
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
                
            for item in data:
                item_name = item.get("title") or item.get("name") or ""
                item_name_clean = item_name.lower().replace(" ", "").replace("_", "")
                
                if hub_query_clean in item_name_clean or item_name_clean in hub_query_clean:
                    lat = item.get("latitude")
                    lon = item.get("longitude")
                    
                    if not lat and "location" in item:
                        lat = item["location"].get("lat")
                        lon = item["location"].get("lon")
                        
                    if lat and lon:
                        return float(lat), float(lon)
        except Exception:
            continue
            
    return None, None

def process_items(items, hub_lat, hub_lon):
    """Calculates distance and sorts a list of items."""
    processed = []
    for item in items:
        new_item = item.copy()
        dist = 0.0
        if hub_lat and item.get("latitude"):
            dist = calculate_haversine(hub_lat, hub_lon, float(item["latitude"]), float(item["longitude"]))
        new_item["distance_miles"] = dist
        processed.append(new_item)
    
    processed.sort(key=lambda x: x["distance_miles"])
    return processed[:5]

def refine_amenities_for_park(park_code: str, data_dir: str = DATA_DIR) -> Dict[str, Any]:
    """
    Programmatic entry point for amenity consolidation for a single park.
    
    Args:
        park_code: The park code (e.g., "BRCA")
        data_dir: Base directory for fixture data
        
    Returns:
        Consolidated amenities data structure
        
    Raises:
        FileNotFoundError: If park directory doesn't exist
    """
    park_dir = os.path.join(data_dir, park_code.upper())
    
    if not os.path.exists(park_dir):
        raise FileNotFoundError(f"Park directory not found: {park_dir}")
    
    amenity_files = [
        f for f in os.listdir(park_dir) 
        if f.startswith("amenities_") and f.endswith(".json") and "consolidated" not in f
    ]
    
    if not amenity_files:
        logger.warning(f"No amenity files found for {park_code}")
        return {"park_code": park_code.upper(), "hubs": {}}
    
    park_consolidated_data = {
        "park_code": park_code.upper(),
        "hubs": {}
    }
    
    for filename in amenity_files:
        slug = filename.replace("amenities_", "").replace(".json", "")
        display_name = slug.replace("_", " ").title()
        
        hub_lat, hub_lon = get_hub_coords(park_code.upper(), slug)
        
        if not hub_lat:
            logger.warning(f"⚠️  Coords not found for hub '{display_name}'. Distances will be 0.")
        
        filepath = os.path.join(park_dir, filename)
        with open(filepath, 'r') as f:
            raw_data = json.load(f)
        
        processed_amenities = {}
        
        for raw_cat, items in raw_data.items():
            clean_cat = CATEGORY_MAP.get(raw_cat)
            if not clean_cat:
                clean_cat = raw_cat.replace(" OR ", "/").title()
            processed_amenities[clean_cat] = process_items(items, hub_lat, hub_lon)
        
        park_consolidated_data["hubs"][display_name] = {
            "location": {"lat": hub_lat, "lon": hub_lon},
            "amenities": processed_amenities
        }
    
    # Save consolidated file
    output_path = os.path.join(park_dir, "amenities_consolidated.json")
    with open(output_path, 'w') as f:
        json.dump(park_consolidated_data, f, indent=2)
    
    logger.info(f"✅ Saved consolidated data for {park_code} to {output_path}")
    return park_consolidated_data


def refine_amenities():
    """Original function for batch processing - loops over TARGET_PARKS."""
    for park_code in TARGET_PARKS:
        logger.info(f"Processing {park_code}...")
        try:
            refine_amenities_for_park(park_code)
        except FileNotFoundError as e:
            logger.warning(f"Skipping {park_code}: {e}")
            continue


if __name__ == "__main__":
    refine_amenities()

