"""
ParkDataFetcher - Centralized service for on-demand park data fetching and refining.

This service provides:
1. Check if fixture data exists for a park
2. Fetch raw NPS data if missing → save to nps/raw/PARK/
3. Run refining scripts → save to ui_fixtures/PARK/
4. Handle incremental updates (e.g., just trails vs. full park)
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Callable

from app.services.data_manager import DataManager
from app.clients.nps_client import NPSClient
import requests

logger = logging.getLogger(__name__)


class ParkDataFetcher:
    """
    Centralized service for on-demand park data fetching and refining.
    Used by both Concierge Chat and Park Explorer Tab to ensure data exists.
    """
    
    # Required fixtures for a "complete" park dataset
    REQUIRED_FIXTURES = [
        "park_details.json",
        "campgrounds.json",
        "visitor_centers.json",
        "webcams.json",
        "things_to_do.json",
        "places.json",
    ]
    
    # Optional but desired fixtures
    OPTIONAL_FIXTURES = [
        "trails_v2.json",       # Requires Gemini enrichment
        "rankings.json",        # Requires AllTrails scraping
        "photo_spots.json",     # Requires blog scraping
        "scenic_drives.json",   # Requires blog scraping
        "amenities_consolidated.json",  # Requires Serper API
    ]
    
    def __init__(self, nps_client: NPSClient = None, data_manager: DataManager = None):
        """
        Initialize with optional injected dependencies.
        """
        self.nps = nps_client
        self.data_manager = data_manager or DataManager()
    
    def has_basic_data(self, park_code: str) -> bool:
        """
        Checks if a park has the minimum required data to be usable.
        Returns True if park_details.json exists.
        """
        return self.data_manager.has_fixture(park_code, "park_details.json")
    
    def has_complete_data(self, park_code: str) -> bool:
        """
        Checks if a park has all required fixture files.
        """
        for fixture in self.REQUIRED_FIXTURES:
            if not self.data_manager.has_fixture(park_code, fixture):
                return False
        return True
    
    def get_missing_fixtures(self, park_code: str) -> List[str]:
        """
        Returns a list of missing fixture filenames.
        """
        missing = []
        for fixture in self.REQUIRED_FIXTURES + self.OPTIONAL_FIXTURES:
            if not self.data_manager.has_fixture(park_code, fixture):
                missing.append(fixture)
        return missing
    
    def fetch_nps_static_data(
        self,
        park_code: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> Dict[str, bool]:
        """
        Fetches all static NPS data for a park and saves to both raw and fixtures directories.
        
        - Raw API responses → data_samples/nps/raw/PARK/
        - Parsed/cleaned data → data_samples/ui_fixtures/PARK/
        
        Args:
            park_code: The park code (e.g., "BRCA")
            progress_callback: Optional callback(current, total, message)
            
        Returns:
            Dict mapping fixture name to success status
        """
        if not self.nps:
            raise ValueError("NPS client not initialized")
        
        park_code = park_code.upper()
        results = {}
        
        # Keywords to filter hikes from things_to_do
        HIKE_KEYWORDS = ['hike', 'trail', 'loop', 'walk', 'trek', 'rim walk']
        
        # Mapping: (fixture_name, raw_name, fetch_function)
        steps = [
            ("park_details.json", "parks.json", lambda: self.nps.get_park_details(park_code)),
            ("campgrounds.json", "campgrounds.json", lambda: self.nps.get_campgrounds(park_code)),
            ("visitor_centers.json", "visitorcenters.json", lambda: self.nps.get_visitor_centers(park_code)),
            ("webcams.json", "webcams.json", lambda: self.nps.get_webcams(park_code)),
            ("things_to_do.json", "thingstodo.json", lambda: self.nps.get_things_to_do(park_code)),
            ("places.json", "places.json", lambda: self.nps.get_places(park_code)),
            ("passport_stamps.json", "passportstamplocations.json", lambda: self.nps.get_passport_stamps(park_code)),
        ]
        
        # Create raw directory
        raw_dir = f"data_samples/nps/raw/{park_code}"
        os.makedirs(raw_dir, exist_ok=True)
        
        total = len(steps)
        for i, (fixture_name, raw_name, fetch_fn) in enumerate(steps):
            if progress_callback:
                progress_callback(i, total, f"Fetching {fixture_name}...")
            
            try:
                data = fetch_fn()
                if data:
                    # Save raw API response
                    raw_path = os.path.join(raw_dir, raw_name)
                    with open(raw_path, 'w') as f:
                        if hasattr(data, 'model_dump'):
                            json.dump(data.model_dump(), f, indent=2)
                        elif isinstance(data, list) and data and hasattr(data[0], 'model_dump'):
                            json.dump([item.model_dump() for item in data], f, indent=2)
                        else:
                            json.dump(data, f, indent=2)
                    logger.info(f"📦 Saved raw {raw_name} for {park_code}")
                    
                    # Filter things_to_do to remove hiking items (they belong in trails)
                    if fixture_name == "things_to_do.json" and isinstance(data, list):
                        original_count = len(data)
                        data = [
                            item for item in data
                            if not any(kw in (item.title if hasattr(item, 'title') else item.get('title', '')).lower() 
                                      for kw in HIKE_KEYWORDS)
                        ]
                        logger.info(f"🔀 Filtered things_to_do: {original_count} → {len(data)} (removed {original_count - len(data)} hike items)")
                    
                    # Save cleaned fixture
                    self.data_manager.save_fixture(park_code, fixture_name, data)
                    results[fixture_name] = True
                    logger.info(f"✅ Saved {fixture_name} for {park_code}")
                    
                    # Auto-generate weather zones for park_details if not already configured
                    if fixture_name == "park_details.json":
                        self._ensure_weather_zones(park_code, data)
                else:
                    results[fixture_name] = False
                    logger.warning(f"⚠️ No data returned for {fixture_name}")
            except Exception as e:
                results[fixture_name] = False
                logger.error(f"❌ Failed to fetch {fixture_name}: {e}")
        
        if progress_callback:
            progress_callback(total, total, "NPS data fetch complete")
        
        return results
    
    def _ensure_weather_zones(self, park_code: str, park_data) -> bool:
        """
        Ensures park_details.json has weather_zones configured.
        If missing, auto-generates default zones based on park location
        and uses Open-Elevation API to get real elevation data.
        
        Weather zones are used for "Weather by Elevation" feature.
        """
        park_code = park_code.upper()
        
        # Load current park_details
        existing = self.data_manager.load_fixture(park_code, "park_details.json")
        if not existing:
            return False
        
        # Check if already configured
        if existing.get("weather_zones") and existing.get("base_weather_zone"):
            logger.info(f"🌡️ Weather zones already configured for {park_code}")
            return True
        
        # Get park location
        location = None
        if hasattr(park_data, 'location'):
            location = park_data.location
        elif isinstance(park_data, dict) and 'location' in park_data:
            location = park_data['location']
        elif isinstance(existing, dict) and 'location' in existing:
            location = existing['location']
        
        if not location:
            logger.warning(f"⚠️ No location found for {park_code}, cannot generate zones")
            return False
        
        # Extract lat/lon
        if hasattr(location, 'lat'):
            base_lat, base_lon = location.lat, location.lon
        elif isinstance(location, dict):
            base_lat, base_lon = location.get('lat'), location.get('lon')
        else:
            logger.warning(f"⚠️ Invalid location format for {park_code}")
            return False
        
        if not base_lat or not base_lon:
            logger.warning(f"⚠️ Missing lat/lon for {park_code}")
            return False
        
        park_name = existing.get("fullName", park_code)
        
        # Generate zone coordinates (3 zones offset from park center)
        zone_coords = [
            {"name": "Valley Floor", "lat": round(base_lat - 0.05, 6), "lon": round(base_lon, 6), 
             "description": f"Lower elevation areas of {park_name}"},
            {"name": "Mid-Elevation", "lat": round(base_lat, 6), "lon": round(base_lon, 6), 
             "description": f"Central areas of {park_name}"},
            {"name": "High Country", "lat": round(base_lat + 0.05, 6), "lon": round(base_lon - 0.03, 6), 
             "description": f"Higher elevation areas of {park_name}"},
        ]
        
        # Lookup real elevations using Open-Elevation API
        ELEVATION_API_URL = "https://api.open-elevation.com/api/v1/lookup"
        
        locations_payload = [{"latitude": z["lat"], "longitude": z["lon"]} for z in zone_coords]
        
        try:
            logger.info(f"🌐 Looking up elevations for {park_code} weather zones...")
            response = requests.post(ELEVATION_API_URL, json={"locations": locations_payload}, timeout=30)
            response.raise_for_status()
            results = response.json().get("results", [])
            
            # Convert meters to feet and add to zones
            weather_zones = []
            for i, zone in enumerate(zone_coords):
                elev_meters = results[i].get("elevation") if i < len(results) else None
                elev_ft = int(elev_meters * 3.28084) if elev_meters is not None else 5000  # Fallback
                
                weather_zones.append({
                    "name": zone["name"],
                    "elevation_ft": elev_ft,
                    "lat": zone["lat"],
                    "lon": zone["lon"],
                    "description": zone["description"]
                })
            
            logger.info(f"🌡️ Elevation lookup successful: {[(z['name'], z['elevation_ft']) for z in weather_zones]}")
            
        except Exception as e:
            logger.warning(f"⚠️ Elevation API failed for {park_code}: {e}. Using default elevations.")
            # Fallback to default elevations
            weather_zones = [
                {"name": z["name"], "elevation_ft": 5000 + i * 2000, "lat": z["lat"], "lon": z["lon"], 
                 "description": z["description"]} 
                for i, z in enumerate(zone_coords)
            ]
        
        # Update the fixture
        existing["weather_zones"] = weather_zones
        existing["base_weather_zone"] = "Mid-Elevation"
        
        # Save updated fixture
        self.data_manager.save_fixture(park_code, "park_details.json", existing)
        zones_summary = [f"{z['name']} ({z['elevation_ft']}ft)" for z in weather_zones]
        logger.info(f"🌡️ Auto-generated weather zones for {park_code}: {zones_summary}")
        
        return True
    
    def fetch_and_classify_trails(
        self,
        park_code: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> bool:
        """
        Fetches places and things_to_do, classifies trail candidates, saves raw_trails.json.
        This prepares the input for refine_trails().
        
        Returns:
            True if successful
        """
        import sys
        sys.path.insert(0, '.')
        
        from scripts.fetch_static_nps import classify_places
        
        park_code = park_code.upper()
        
        if progress_callback:
            progress_callback(0, 2, "Classifying trail candidates...")
        
        # Load raw places and thingstodo from RAW directory (to avoid pre-filtered fixtures)
        raw_dir = f"data_samples/nps/raw/{park_code}"
        
        places_path = f"{raw_dir}/places.json"
        places_raw = []
        if os.path.exists(places_path):
            try:
                with open(places_path, 'r') as f:
                    data = json.load(f)
                    # Handle typical NPS API structure (dict with 'data' or list)
                    places_raw = data.get('data', []) if isinstance(data, dict) else data
            except Exception as e:
                logger.error(f"Failed to load raw places.json: {e}")
        
        things_path = f"{raw_dir}/thingstodo.json"
        things_raw = []
        if os.path.exists(things_path):
            try:
                with open(things_path, 'r') as f:
                    data = json.load(f)
                    things_raw = data.get('data', []) if isinstance(data, dict) else data
            except Exception as e:
                logger.error(f"Failed to load raw thingstodo.json: {e}")
        
        if not places_raw and not things_raw:
             # Fallback to fixtures if raw files missing (backward compatibility)
             logger.warning(f"⚠️ Raw data missing for {park_code}, falling back to fixtures (may be filtered)")
             places_raw = self.data_manager.load_fixture(park_code, "places.json")
             things_raw = self.data_manager.load_fixture(park_code, "things_to_do.json")
             
             if not places_raw and not things_raw:
                raise FileNotFoundError(f"No places or things_to_do data found for {park_code}")
        
        # Combine items
        combined_items = {}
        for item in (places_raw or []):
            if isinstance(item, dict):
                combined_items[item.get("id", str(len(combined_items)))] = item
        for item in (things_raw or []):
            if isinstance(item, dict):
                combined_items[item.get("id", str(len(combined_items)))] = item
        
        merged_data = {"data": list(combined_items.values())}
        
        # Run classification
        trails_raw, things_raw_classified = classify_places(merged_data)
        
        if progress_callback:
            progress_callback(1, 2, f"Found {len(trails_raw.get('data', []))} trail candidates...")
        
        # Save raw_trails.json to nps/raw directory
        raw_dir = f"data_samples/nps/raw/{park_code}"
        os.makedirs(raw_dir, exist_ok=True)
        
        with open(f"{raw_dir}/raw_trails.json", "w") as f:
            json.dump(trails_raw, f, indent=2)
        
        if progress_callback:
            progress_callback(2, 2, "Trail classification complete")
        
        logger.info(f"✅ Saved raw_trails.json with {len(trails_raw.get('data', []))} candidates")
        return True
    
    def refine_trails(
        self,
        park_code: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> List[Dict]:
        """
        Runs Gemini enrichment on raw trail candidates.
        Requires raw_trails.json to exist in nps/raw/PARK/.
        
        Returns:
            List of enriched trail dictionaries
        """
        import sys
        sys.path.insert(0, '.')
        
        from scripts.refine_trails_with_gemini import refine_trails
        
        return refine_trails(park_code, progress_callback)
    
    def fetch_rankings(
        self,
        park_code: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> int:
        """
        Fetches AllTrails rankings and merges with trails_v2.json.
        
        Returns:
            Number of trails affected
        """
        import sys
        sys.path.insert(0, '.')
        
        from scripts.fetch_rankings import fetch_and_merge_rankings
        
        return fetch_and_merge_rankings(park_code, progress_callback)
    
    def fetch_photo_spots(
        self,
        park_code: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> List[Dict]:
        """
        Fetches photo spots from blogs.
        
        Returns:
            List of photo spot dictionaries
        """
        import sys
        sys.path.insert(0, '.')
        
        from scripts.fetch_photo_spots import fetch_photo_spots_for_park
        
        return fetch_photo_spots_for_park(park_code, progress_callback)
    
    def fetch_scenic_drives(
        self,
        park_code: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> List[Dict]:
        """
        Fetches scenic drives from blogs.
        
        Returns:
            List of scenic drive dictionaries
        """
        import sys
        sys.path.insert(0, '.')
        
        from scripts.fetch_scenic_drives import fetch_scenic_drives_for_park
        
        return fetch_scenic_drives_for_park(park_code, progress_callback)
    
    def fetch_amenities(
        self,
        park_code: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> Dict[str, Any]:
        """
        Fetches amenities (gas, restaurants, etc.) near park entrances using Serper API,
        then consolidates them.
        
        Returns:
            Consolidated amenities data
        """
        import sys
        sys.path.insert(0, '.')
        
        from scripts.admin_fetch_amenities import fetch_amenities_for_park
        from scripts.refine_amenities import refine_amenities_for_park
        
        park_code = park_code.upper()
        
        # Step 1: Fetch raw amenities from Serper/Google Maps
        if progress_callback:
            progress_callback(0, 2, "Searching for nearby amenities...")
        
        result = fetch_amenities_for_park(
            park_code,
            nps_client=self.nps,
            data_manager=self.data_manager,
            progress_callback=progress_callback
        )
        
        # Step 2: Consolidate amenities
        if progress_callback:
            progress_callback(1, 2, "Consolidating amenity data...")
        
        try:
            consolidated = refine_amenities_for_park(park_code)
        except FileNotFoundError:
            # If no amenity files exist, return the raw result
            consolidated = result
        
        if progress_callback:
            progress_callback(2, 2, f"Found amenities for {len(result.get('hubs', {}))} hubs")
        
        return consolidated
    
    def ensure_park_data(
        self,
        park_code: str,
        include_trails: bool = True,
        include_rankings: bool = True,
        include_photo_spots: bool = True,
        include_scenic_drives: bool = True,
        include_amenities: bool = True,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: Ensures all required data exists for a park.
        Fetches and refines missing data as needed.
        
        Args:
            park_code: The park code (e.g., "BRCA")
            include_trails: Whether to include trail enrichment (slow)
            include_rankings: Whether to include AllTrails data (slow)
            include_photo_spots: Whether to include photo spots (expensive)
            include_scenic_drives: Whether to include scenic drives (expensive)
            include_amenities: Whether to include amenities (requires pre-fetch)
            progress_callback: Optional callback(current, total, message)
            
        Returns:
            Dict with status of each operation
        """
        park_code = park_code.upper()
        status = {"park_code": park_code, "operations": {}}
        
        # Step 1: NPS Static Data - Fetch if ANY required fixture is missing
        missing_required = [f for f in self.REQUIRED_FIXTURES 
                          if not self.data_manager.has_fixture(park_code, f)]
        
        if missing_required:
            if progress_callback:
                progress_callback(0, 4, f"Fetching NPS data (missing: {', '.join(missing_required)})...")
            try:
                result = self.fetch_nps_static_data(park_code, progress_callback)
                status["operations"]["nps_data"] = result
                logger.info(f"📦 Fetched missing fixtures for {park_code}: {missing_required}")
            except Exception as e:
                status["operations"]["nps_data"] = {"error": str(e)}
                logger.error(f"NPS data fetch failed: {e}")
        else:
            status["operations"]["nps_data"] = "already_exists"
        
        # Step 2: Trail classification and refinement
        if include_trails:
            if not self.data_manager.has_fixture(park_code, "trails_v2.json"):
                # Pre-check: Ensure places.json exists (critical for trail classification)
                if not self.data_manager.has_fixture(park_code, "places.json"):
                    logger.warning(f"⚠️ places.json missing for {park_code}, fetching before trail classification...")
                    try:
                        places = self.nps.get_places(park_code)
                        if places:
                            self.data_manager.save_fixture(park_code, "places.json", places)
                            logger.info(f"✅ Fetched places.json for {park_code}")
                    except Exception as e:
                        logger.error(f"Failed to fetch places.json: {e}")
                
                if progress_callback:
                    progress_callback(1, 4, "Processing trails...")
                try:
                    self.fetch_and_classify_trails(park_code, progress_callback)
                    trails = self.refine_trails(park_code, progress_callback)
                    status["operations"]["trails"] = {"count": len(trails)}
                except Exception as e:
                    status["operations"]["trails"] = {"error": str(e)}
                    logger.error(f"Trail processing failed: {e}")
            else:
                status["operations"]["trails"] = "already_exists"
        
        # Step 3: AllTrails rankings
        if include_rankings:
            if not self.data_manager.has_fixture(park_code, "rankings.json"):
                if progress_callback:
                    progress_callback(2, 4, "Fetching AllTrails rankings...")
                try:
                    count = self.fetch_rankings(park_code, progress_callback)
                    status["operations"]["rankings"] = {"count": count}
                except Exception as e:
                    status["operations"]["rankings"] = {"error": str(e)}
                    logger.error(f"Rankings fetch failed: {e}")
            else:
                status["operations"]["rankings"] = "already_exists"
        
        # Step 4: Photo spots (optional)
        if include_photo_spots:
            if not self.data_manager.has_fixture(park_code, "photo_spots.json"):
                if progress_callback:
                    progress_callback(3, 4, "Fetching photo spots...")
                try:
                    spots = self.fetch_photo_spots(park_code, progress_callback)
                    status["operations"]["photo_spots"] = {"count": len(spots)}
                except Exception as e:
                    status["operations"]["photo_spots"] = {"error": str(e)}
                    logger.error(f"Photo spots fetch failed: {e}")
            else:
                status["operations"]["photo_spots"] = "already_exists"
        
        # Step 5: Scenic drives (optional)
        if include_scenic_drives:
            if not self.data_manager.has_fixture(park_code, "scenic_drives.json"):
                if progress_callback:
                    progress_callback(4, 6, "Fetching scenic drives...")
                try:
                    drives = self.fetch_scenic_drives(park_code, progress_callback)
                    status["operations"]["scenic_drives"] = {"count": len(drives)}
                except Exception as e:
                    status["operations"]["scenic_drives"] = {"error": str(e)}
                    logger.error(f"Scenic drives fetch failed: {e}")
            else:
                status["operations"]["scenic_drives"] = "already_exists"
        
        # Step 6: Amenities
        if include_amenities:
            if not self.data_manager.has_fixture(park_code, "amenities_consolidated.json"):
                if progress_callback:
                    progress_callback(5, 6, "Fetching nearby amenities...")
                try:
                    amenities = self.fetch_amenities(park_code, progress_callback)
                    status["operations"]["amenities"] = {"hubs": len(amenities.get("hubs", {}))}
                except Exception as e:
                    status["operations"]["amenities"] = {"error": str(e)}
                    logger.error(f"Amenities fetch failed: {e}")
            else:
                status["operations"]["amenities"] = "already_exists"
        
        if progress_callback:
            progress_callback(6, 6, "Data setup complete!")
        
        return status
