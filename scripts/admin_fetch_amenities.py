import os
import logging
from typing import Dict, List, Any, Callable
from dotenv import load_dotenv

# App Imports
from app.clients.nps_client import NPSClient
from app.clients.external_client import ExternalClient
from app.utils.geospatial import mine_entrances
from app.services.data_manager import DataManager

# Setup
logging.basicConfig(level=logging.INFO)
load_dotenv()

logger = logging.getLogger(__name__)

# Configuration
TARGET_PARKS = ["ZION", "BRCA"]  # Used for CLI mode

TASKS = [
    ("urgent care OR hospital OR emergency room", "10z"),
    ("gas station", "11z"),
    ("ev charging", "10z"),
    ("restaurant", "11z"),
    ("grocery store", "11z")
]


def fetch_amenities_for_park(
    park_code: str,
    nps_client: NPSClient = None,
    external_client: ExternalClient = None,
    data_manager: DataManager = None,
    progress_callback: Callable[[int, int, str], None] = None
) -> Dict[str, Any]:
    """
    Programmatic entry point for fetching amenities for a single park.
    
    Args:
        park_code: The park code (e.g., "BRCA")
        nps_client: Optional NPS client (will create if not provided)
        external_client: Optional external client (will create if not provided)
        data_manager: Optional data manager
        progress_callback: Optional callback(current, total, message)
        
    Returns:
        Dict with hubs and their amenities
        
    Raises:
        ValueError: If API keys not found
    """
    park_code = park_code.upper()
    
    nps_key = os.getenv("NPS_API_KEY")
    serper_key = os.getenv("SERPER_API_KEY")
    
    if not nps_key:
        raise ValueError("NPS_API_KEY not found in environment")
    if not serper_key:
        raise ValueError("SERPER_API_KEY not found in environment")
    
    # Initialize clients if not provided
    nps = nps_client or NPSClient(api_key=nps_key)
    ext = external_client or ExternalClient(serper_key=serper_key)
    dm = data_manager or DataManager()
    
    if progress_callback:
        progress_callback(0, 3, f"Finding park entrances for {park_code}...")
    
    # 1. Discover Entrances
    places = [p.model_dump() for p in nps.get_places(park_code)]
    vcs = [v.model_dump() for v in nps.get_visitor_centers(park_code)]
    entrances = mine_entrances(park_code, places, vcs)
    
    logger.info(f"Found {len(entrances)} hubs for {park_code}")
    
    if not entrances:
        logger.warning(f"No entrances found for {park_code}")
        return {"park_code": park_code, "hubs": {}}
    
    result = {"park_code": park_code, "hubs": {}}
    total_tasks = len(entrances) * len(TASKS)
    completed = 0
    
    for i, ent in enumerate(entrances):
        name = ent["name"]
        lat = ent["lat"]
        lon = ent["lon"]
        
        if progress_callback:
            progress_callback(i + 1, len(entrances) + 1, f"Searching amenities near {name}...")
        
        # Check existing data
        current_data = dm.load_amenities(park_code, name)
        changes = False
        
        # Run tasks
        for query, zoom in TASKS:
            if query in current_data and current_data[query]:
                completed += 1
                continue
            
            try:
                amenities = ext.search_maps(query, lat, lon, zoom)
                current_data[query] = [a.model_dump() for a in amenities]
                changes = True
                completed += 1
            except Exception as e:
                logger.error(f"Error fetching {query} for {name}: {e}")
        
        # Save
        if changes:
            dm.save_amenities(park_code, name, current_data)
        
        result["hubs"][name] = {
            "location": {"lat": lat, "lon": lon},
            "amenities": current_data
        }
    
    if progress_callback:
        progress_callback(len(entrances) + 1, len(entrances) + 1, f"Completed amenity fetch for {park_code}")
    
    return result


def main():
    """CLI entry point for manual execution."""
    print("--- 🛠️ Admin Tool: Pre-Fetch Park Amenities ---")
    
    nps_key = os.getenv("NPS_API_KEY")
    serper_key = os.getenv("SERPER_API_KEY")
    
    if not all([nps_key, serper_key]):
        print("❌ Missing API Keys.")
        return

    nps = NPSClient(api_key=nps_key)
    ext = ExternalClient(serper_key=serper_key)
    dm = DataManager()
    
    for park_code in TARGET_PARKS:
        print(f"\n🌲 Processing {park_code}...")
        
        def cli_progress(current, total, message):
            print(f"  [{current}/{total}] {message}")
        
        try:
            result = fetch_amenities_for_park(
                park_code,
                nps_client=nps,
                external_client=ext,
                data_manager=dm,
                progress_callback=cli_progress
            )
            print(f"  ✅ Found {len(result['hubs'])} hubs")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    print("\n✅ All Parks Updated.")


if __name__ == "__main__":
    main()
