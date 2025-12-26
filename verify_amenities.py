import os
import json
import logging
from dotenv import load_dotenv

# App Imports
from app.clients.external_client import ExternalClient
from app.models import Amenity

# Setup
logging.basicConfig(level=logging.INFO)
load_dotenv()

# We save results into the same UI Fixtures directory structure
# This assumes the user wants it in 'data_samples/ui_fixtures/ZION'
OUTPUT_DIR_BASE = "data_samples/ui_fixtures"
TARGET_PARK = "ZION"

# Zion Entrances
ZION_ENTRANCES = [
    {"name": "Zion Canyon Visitor Center", "lat": 37.2001, "lon": -112.9869},
    {"name": "Kolob Canyons Visitor Center", "lat": 37.4536, "lon": -113.2257}
]

# Task Config
TASKS = [
    ("urgent care OR hospital OR emergency room", "10z"),
    ("gas station OR ev charging", "11z"),
    ("restaurant OR grocery store", "11z")
]

def get_amenities_file_path(entrance_name):
    # Sanitize name for filename
    safe_name = entrance_name.replace(" ", "_").lower()
    filename = f"amenities_{safe_name}.json"

    # Ensure directory exists
    park_dir = os.path.join(OUTPUT_DIR_BASE, TARGET_PARK)
    os.makedirs(park_dir, exist_ok=True)

    return os.path.join(park_dir, filename)

def load_existing_data(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    print(f"--- 🗺️ Verifying Serper Maps Endpoint for {TARGET_PARK} (Per Entrance) ---")

    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key:
        print("❌ SERPER_API_KEY not found in .env")
        return

    ext = ExternalClient(serper_key=serper_key)

    for entrance in ZION_ENTRANCES:
        entrance_name = entrance["name"]
        lat = entrance["lat"]
        lon = entrance["lon"]

        print(f"\n📍 Processing {entrance_name}...")

        # 1. Determine file path for this entrance
        filepath = get_amenities_file_path(entrance_name)

        # 2. Load existing data for this entrance
        entrance_data = load_existing_data(filepath)

        changes_made = False

        # 3. Iterate tasks
        for query_text, zoom in TASKS:
            # Check if this query already has results
            if query_text in entrance_data and entrance_data[query_text]:
                count = len(entrance_data[query_text])
                print(f"   ✅ Using CACHED results for '{query_text}' (Count: {count})")
                continue

            # If not cached, query API
            print(f"   🚀 Fetching '{query_text}' at {zoom}...")
            try:
                amenities = ext.search_maps(query_text, lat, lon, zoom)

                # Serialize Pydantic models
                serialized = [a.model_dump() for a in amenities]

                # Store in dict keyed by query
                entrance_data[query_text] = serialized
                changes_made = True
                print(f"      -> Fetched {len(serialized)} items.")

            except Exception as e:
                print(f"      ❌ Error: {e}")

        # 4. Save if updated
        if changes_made:
            save_data(filepath, entrance_data)
            print(f"   💾 Updated {filepath}")
        else:
            print(f"   💾 No API calls needed (all cached in {filepath}).")

if __name__ == "__main__":
    main()