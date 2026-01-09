#!/usr/bin/env python3
"""
Enrich trail data with trailhead elevations and assign weather zones.

Uses the Open-Elevation API to lookup elevations from lat/lon coordinates,
then assigns each trail to the nearest weather zone.

Usage:
    python scripts/enrich_trail_elevations.py BRCA
"""

import json
import sys
import time
import requests
from pathlib import Path
from typing import List, Dict, Optional

# Open-Elevation API (free, no auth required)
ELEVATION_API_URL = "https://api.open-elevation.com/api/v1/lookup"

def load_park_details(park_code: str) -> Dict:
    """Load park_details.json for a park."""
    path = Path(f"data_samples/ui_fixtures/{park_code}/park_details.json")
    if not path.exists():
        raise FileNotFoundError(f"Park details not found: {path}")
    with open(path, "r") as f:
        return json.load(f)

def load_trails(park_code: str) -> List[Dict]:
    """Load trails_v2.json for a park."""
    path = Path(f"data_samples/ui_fixtures/{park_code}/trails_v2.json")
    if not path.exists():
        raise FileNotFoundError(f"Trails not found: {path}")
    with open(path, "r") as f:
        return json.load(f)

def save_trails(park_code: str, trails: List[Dict]) -> None:
    """Save enriched trails back to trails_v2.json."""
    path = Path(f"data_samples/ui_fixtures/{park_code}/trails_v2.json")
    with open(path, "w") as f:
        json.dump(trails, f, indent=2)
    print(f"✅ Saved {len(trails)} trails to {path}")

def batch_lookup_elevations(locations: List[Dict[str, float]]) -> List[Optional[int]]:
    """
    Lookup elevations for multiple locations using Open-Elevation API.
    Returns list of elevations in feet (or None if lookup failed).
    """
    if not locations:
        return []
    
    # API expects list of {"latitude": x, "longitude": y}
    payload = {"locations": locations}
    
    try:
        response = requests.post(ELEVATION_API_URL, json=payload, timeout=30)
        response.raise_for_status()
        results = response.json().get("results", [])
        
        # Convert meters to feet
        elevations = []
        for r in results:
            elev_m = r.get("elevation")
            if elev_m is not None:
                elevations.append(int(elev_m * 3.28084))  # meters to feet
            else:
                elevations.append(None)
        return elevations
    except Exception as e:
        print(f"⚠️ Elevation lookup failed: {e}")
        return [None] * len(locations)

def assign_zone(elevation_ft: int, zones: List[Dict]) -> str:
    """
    Assign a trail to the nearest weather zone based on elevation.
    Returns the zone name.
    """
    if not zones or elevation_ft is None:
        return None
    
    closest_zone = None
    min_diff = float("inf")
    
    for zone in zones:
        diff = abs(elevation_ft - zone["elevation_ft"])
        if diff < min_diff:
            min_diff = diff
            closest_zone = zone["name"]
    
    return closest_zone

def enrich_trails(park_code: str) -> None:
    """Main enrichment logic."""
    print(f"\n🔄 Enriching trails for {park_code}...")
    
    # Load data
    park_details = load_park_details(park_code)
    trails = load_trails(park_code)
    zones = park_details.get("weather_zones", [])
    
    if not zones:
        print(f"⚠️ No weather_zones defined in park_details.json for {park_code}")
        return
    
    print(f"📍 Found {len(zones)} weather zones: {[z['name'] for z in zones]}")
    print(f"🥾 Processing {len(trails)} trails...")
    
    # Collect locations that need elevation lookup
    locations_to_lookup = []
    trail_indices = []
    
    for i, trail in enumerate(trails):
        # Skip if already enriched
        if trail.get("trailhead_elevation_ft") and trail.get("weather_zone"):
            continue
        
        loc = trail.get("location")
        if loc and loc.get("lat") and loc.get("lon"):
            locations_to_lookup.append({
                "latitude": loc["lat"],
                "longitude": loc["lon"]
            })
            trail_indices.append(i)
    
    if not locations_to_lookup:
        print("✅ All trails already enriched!")
        return
    
    print(f"🌐 Looking up elevations for {len(locations_to_lookup)} trails...")
    
    # Batch lookup in chunks (API may have limits)
    BATCH_SIZE = 50
    all_elevations = []
    
    for i in range(0, len(locations_to_lookup), BATCH_SIZE):
        batch = locations_to_lookup[i:i + BATCH_SIZE]
        print(f"   Batch {i//BATCH_SIZE + 1}/{(len(locations_to_lookup)-1)//BATCH_SIZE + 1}...")
        elevations = batch_lookup_elevations(batch)
        all_elevations.extend(elevations)
        time.sleep(0.5)  # Be nice to the free API
    
    # Apply elevations and assign zones
    enriched_count = 0
    for idx, elev in zip(trail_indices, all_elevations):
        if elev is not None:
            trails[idx]["trailhead_elevation_ft"] = elev
            trails[idx]["weather_zone"] = assign_zone(elev, zones)
            enriched_count += 1
    
    print(f"✅ Enriched {enriched_count} trails with elevations and zones")
    
    # Save results
    save_trails(park_code, trails)
    
    # Print summary
    print("\n📊 Zone Distribution:")
    zone_counts = {}
    for trail in trails:
        zone = trail.get("weather_zone", "Unknown")
        zone_counts[zone] = zone_counts.get(zone, 0) + 1
    for zone, count in sorted(zone_counts.items()):
        print(f"   {zone}: {count} trails")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/enrich_trail_elevations.py PARK_CODE")
        print("Example: python scripts/enrich_trail_elevations.py BRCA")
        sys.exit(1)
    
    park_code = sys.argv[1].upper()
    enrich_trails(park_code)
