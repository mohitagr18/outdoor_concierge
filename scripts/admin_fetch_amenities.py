import os
import logging
from dotenv import load_dotenv

# App Imports
from app.clients.nps_client import NPSClient
from app.clients.external_client import ExternalClient
from app.utils.geospatial import mine_entrances
from app.services.data_manager import DataManager

# Setup
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Configuration
TARGET_PARKS = ["ZION"] # Add more as needed
TASKS = [
    ("urgent care OR hospital OR emergency room", "10z"),
    ("gas station", "11z"),
    ("ev charging", "10z"),
    ("restaurant", "11z"),
    ("grocery store", "11z")
]

def main():
    print("--- 🛠️ Admin Tool: Pre-Fetch Park Amenities ---")
    
    nps_key = os.getenv("NPS_API_KEY")
    serper_key = os.getenv("SERPER_API_KEY")
    
    if not all([nps_key, serper_key]):
        print("❌ Missing API Keys.")
        return

    # Init Services
    nps = NPSClient(api_key=nps_key)
    ext = ExternalClient(serper_key=serper_key)
    dm = DataManager()
    
    for park_code in TARGET_PARKS:
        print(f"\n🌲 Processing {park_code}...")
        
        # 1. Discover Entrances
        print("   Mining entrances...")
        places = [p.model_dump() for p in nps.get_places(park_code)]
        vcs = [v.model_dump() for v in nps.get_visitor_centers(park_code)]
        entrances = mine_entrances(park_code, places, vcs)
        
        print(f"   Found {len(entrances)} hubs.")
        
        for ent in entrances:
            name = ent["name"]
            lat = ent["lat"]
            lon = ent["lon"]
            print(f"   📍 Hub: {name}")
            
            # 2. Check Existing Data
            current_data = dm.load_amenities(park_code, name)
            changes = False
            
            # 3. Run Tasks
            for query, zoom in TASKS:
                if query in current_data and current_data[query]:
                    print(f"      ✅ Cached: {query}")
                    continue
                
                print(f"      🚀 Fetching: {query} ({zoom})")
                try:
                    amenities = ext.search_maps(query, lat, lon, zoom)
                    current_data[query] = [a.model_dump() for a in amenities]
                    changes = True
                except Exception as e:
                    print(f"      ❌ Error: {e}")
            
            # 4. Save
            if changes:
                dm.save_amenities(park_code, name, current_data)
                print("      💾 Saved.")

    print("\n✅ All Parks Updated.")

if __name__ == "__main__":
    main()
