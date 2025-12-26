import os
import json
import logging
import math
from typing import List, Dict, Any

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Refiner")

# Configuration
DATA_DIR = "data_samples/ui_fixtures"
TARGET_PARKS = ["ZION"] # Add YOSE, GRCA later
OUTPUT_FILENAME = "amenities_consolidated.json"

def calculate_haversine(lat1, lon1, lat2, lon2):
    """
    Returns straight-line distance in miles.
    Used for sorting candidates to find the 'Nearest 5' without incurring API costs.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 9999.9
    
    try:
        R = 3958.8 # Earth radius in miles
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(R * c, 2)
    except (ValueError, TypeError):
        return 9999.9

def load_hub_coords(park_code, entrance_name):
    """
    Attempts to lookup the original Entrance/VC coordinates from raw NPS files.
    """
    park_dir = os.path.join(DATA_DIR, park_code)
    
    # Check both VCs and Places files
    for fname in ["visitor_centers.json", "places.json"]:
        fpath = os.path.join(park_dir, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, 'r') as f:
                    data = json.load(f)
                    for item in data:
                        # Normalize names for matching
                        i_name = item.get("name") or item.get("title") or ""
                        if i_name.lower().replace(" ", "") == entrance_name.lower().replace(" ", ""):
                            # Found it! Return coords
                            if "latitude" in item and item["latitude"]:
                                return float(item["latitude"]), float(item["longitude"])
            except:
                continue
    
    return None, None

def refine_park(park_code):
    park_dir = os.path.join(DATA_DIR, park_code)
    consolidated_data = {}
    
    # 1. Scan for amenity files
    files = [f for f in os.listdir(park_dir) if f.startswith("amenities_") and f.endswith(".json") and "consolidated" not in f]
    
    if not files:
        logger.warning(f"No amenity files found for {park_code}")
        return

    logger.info(f"Processing {len(files)} amenity files for {park_code}...")

    for filename in files:
        # Reconstruct Display Name from filename
        # e.g. "amenities_zion_canyon_visitor_center.json" -> "Zion Canyon Visitor Center"
        slug = filename.replace("amenities_", "").replace(".json", "")
        display_name = slug.replace("_", " ").title()
        
        # Special case fixups (optional)
        if "Ev" in display_name: display_name = display_name.replace("Ev", "EV")
        
        # Lookup Origin Coords
        hub_lat, hub_lon = load_hub_coords(park_code, display_name)
        
        if not hub_lat:
            logger.warning(f"Could not find origin coords for '{display_name}'. Distances will be 0.")
        
        filepath = os.path.join(park_dir, filename)
        with open(filepath, 'r') as f:
            raw_data = json.load(f)
            
        refined_hub_data = {}
        
        for category, items in raw_data.items():
            valid_items = []
            for item in items:
                dist = 0.0
                if hub_lat and item.get("latitude"):
                    dist = calculate_haversine(hub_lat, hub_lon, item["latitude"], item["longitude"])
                
                # Add computed field
                item["distance_miles_approx"] = dist
                valid_items.append(item)
            
            # Sort by distance Ascending
            valid_items.sort(key=lambda x: x["distance_miles_approx"])
            
            # Slice Top 5
            refined_hub_data[category] = valid_items[:5]
            
        consolidated_data[display_name] = refined_hub_data
        
    # Save Consolidated
    out_path = os.path.join(park_dir, OUTPUT_FILENAME)
    with open(out_path, 'w') as f:
        json.dump(consolidated_data, f, indent=2)
    
    logger.info(f"✅ Saved consolidated data to {out_path}")

if __name__ == "__main__":
    for park in TARGET_PARKS:
        refine_park(park)
