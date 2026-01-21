#!/usr/bin/env python3
"""
Debug Tool: Park Trail Data Investigation

This script diagnoses issues with trail data for any National Park by:
1. Fetching raw data from the NPS "places" and "thingstodo" endpoints
2. Analyzing which items would be classified as trails
3. Comparing with current local fixture data
4. Identifying gaps and data quality issues

Usage:
    python scripts/debug_park_trails.py GLAC       # Investigate Glacier NP
    python scripts/debug_park_trails.py ZION       # Investigate Zion NP
    python scripts/debug_park_trails.py YOSE --save  # Investigate + save API response
    python scripts/debug_park_trails.py BRCA --verbose  # Full item details

Arguments:
    PARK_CODE    Required. The NPS park code (e.g., GLAC, ZION, YOSE, BRCA)
    --save       Optional. Save full API responses to nps/raw/{PARK}/debug_*.json
    --verbose    Optional. Show detailed analysis for each item
    --compare    Optional. Compare with another park (e.g., --compare ZION)
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Ensure project root is in path
sys.path.insert(0, os.getcwd())

load_dotenv()

from app.clients.nps_client import NPSClient
from app.services.data_manager import DataManager

# Classification keywords (same as fetch_static_nps.py)
HIKE_KEYWORDS = [
    "trail", "trailhead", "hike", "hiking", "route", "walk", "loop", "path", 
    "canyon", "rim", "overlook", "point", "junction", "narrows", "landing", 
    "bridge", "mesa", "wash", "access"
]

INFRASTRUCTURE_KEYWORDS = [
    "visitor center", "museum", "gift shop", "campground", "lodging", 
    "picnic", "restroom", "amphitheater", "station", "office", "entrance", 
    "exhibit", "wayside", "marker", "shuttle stop", "bus stop", "parking",
    "residence", "village", "hotel", "store", "school", "church"
]

CONTENT_INDICATORS = ["miles", "km", "elevation", "round-trip", "strenuous", "moderate", "easy", "climb", "hike"]


def divider(title: str, char: str = "="):
    """Print a section divider."""
    width = 70
    print(f"\n{char * width}")
    print(f" {title}")
    print(f"{char * width}\n")


def contains_whole_word(text: str, keyword: str) -> bool:
    """Check if a whole word exists in text."""
    pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
    return bool(re.search(pattern, text.lower()))


def analyze_item(item: dict) -> dict:
    """Analyze a single NPS item for trail classification signals."""
    title = item.get("title", "Unknown")
    
    # Get all description fields
    desc_fields = {
        "shortDescription": item.get("shortDescription", ""),
        "longDescription": item.get("longDescription", ""),
        "listingDescription": item.get("listingDescription", ""),
        "bodyText": item.get("bodyText", ""),
        "activityDescription": item.get("activityDescription", ""),
    }
    
    desc_combined = " ".join(v for v in desc_fields.values() if v)
    title_lower = title.lower()
    desc_lower = desc_combined.lower()
    
    # Classification analysis
    found_hike_kw = [kw for kw in HIKE_KEYWORDS if contains_whole_word(title_lower, kw)]
    found_infra_kw = [kw for kw in INFRASTRUCTURE_KEYWORDS if contains_whole_word(title_lower, kw)]
    found_content = [w for w in CONTENT_INDICATORS if w in desc_lower]
    
    # Activities from the item
    activities = item.get("activities", [])
    activity_names = [a.get("name", "") for a in activities]
    has_hiking_activity = "Hiking" in activity_names
    
    # Location check
    location = item.get("location")
    has_location = False
    if isinstance(location, dict):
        has_location = bool(location.get("lat") and location.get("lon"))
    
    # Classification logic (mirrors classify_places in fetch_static_nps.py)
    is_infrastructure = any(contains_whole_word(title_lower, kw) for kw in INFRASTRUCTURE_KEYWORDS)
    has_hike_keyword = any(contains_whole_word(title_lower, kw) for kw in HIKE_KEYWORDS)
    has_content_indicators = sum(1 for w in CONTENT_INDICATORS if w in desc_lower) >= 2
    
    would_classify = False
    if is_infrastructure:
        would_classify = False
    elif has_hike_keyword:
        would_classify = True
    elif has_content_indicators:
        would_classify = True
    
    # Overlook/Point special handling
    if contains_whole_word(title_lower, "overlook") or contains_whole_word(title_lower, "point"):
        is_hike_desc = "trail" in desc_lower or "hike" in desc_lower
        if not has_content_indicators and not is_hike_desc:
            would_classify = False
    
    return {
        "title": title,
        "id": item.get("id", ""),
        "description_length": len(desc_combined),
        "description_preview": desc_combined[:150] + "..." if len(desc_combined) > 150 else desc_combined,
        "hike_keywords_found": found_hike_kw,
        "infrastructure_keywords_found": found_infra_kw,
        "content_indicators_found": found_content,
        "activities": activity_names,
        "has_hiking_activity": has_hiking_activity,
        "has_location": has_location,
        "duration": item.get("duration", ""),
        "would_classify_as_trail": would_classify,
        "classification_reason": (
            "infrastructure" if is_infrastructure else
            "hike_keyword" if has_hike_keyword else
            "content_indicators" if has_content_indicators else
            "no_match"
        )
    }


def fetch_park_data(nps: NPSClient, park_code: str) -> tuple:
    """Fetch places and thingstodo data from NPS API."""
    print(f"📡 Fetching 'places' for {park_code}...")
    places_raw = nps._get("places", params={"parkCode": park_code, "limit": 500}, headers=nps._get_headers())
    places_count = len(places_raw.get("data", []))
    print(f"   → Received {places_count} places")
    
    print(f"📡 Fetching 'thingstodo' for {park_code}...")
    things_raw = nps._get("thingstodo", params={"parkCode": park_code, "limit": 500}, headers=nps._get_headers())
    things_count = len(things_raw.get("data", []))
    print(f"   → Received {things_count} things to do")
    
    return places_raw, things_raw


def analyze_endpoint(data: dict, endpoint_name: str, verbose: bool = False) -> dict:
    """Analyze an NPS endpoint's data."""
    items = data.get("data", [])
    stats = {
        "total": len(items),
        "trail_candidates": 0,
        "with_hiking_activity": 0,
        "with_location": 0,
        "items": []
    }
    
    for item in items:
        analysis = analyze_item(item)
        stats["items"].append(analysis)
        
        if analysis["would_classify_as_trail"]:
            stats["trail_candidates"] += 1
        if analysis["has_hiking_activity"]:
            stats["with_hiking_activity"] += 1
        if analysis["has_location"]:
            stats["with_location"] += 1
    
    return stats


def check_local_fixtures(dm: DataManager, park_code: str) -> dict:
    """Check what fixture files exist locally."""
    files_to_check = [
        "park_details.json",
        "places.json", 
        "things_to_do.json",
        "trails_v2.json",
        "rankings.json",
        "photo_spots.json",
        "scenic_drives.json"
    ]
    
    status = {}
    for f in files_to_check:
        exists = dm.has_fixture(park_code, f)
        data = None
        count = None
        
        if exists:
            data = dm.load_fixture(park_code, f)
            if isinstance(data, list):
                count = len(data)
            elif isinstance(data, dict) and "data" in data:
                count = len(data["data"])
        
        status[f] = {"exists": exists, "count": count}
    
    return status


def main():
    parser = argparse.ArgumentParser(
        description="Debug tool for investigating park trail data issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/debug_park_trails.py GLAC
  python scripts/debug_park_trails.py ZION --save
  python scripts/debug_park_trails.py YOSE --verbose
  python scripts/debug_park_trails.py GRCA --compare ZION
        """
    )
    parser.add_argument("park_code", type=str, help="NPS park code (e.g., GLAC, ZION)")
    parser.add_argument("--save", action="store_true", help="Save full API responses to files")
    parser.add_argument("--verbose", action="store_true", help="Show detailed analysis for each item")
    parser.add_argument("--compare", type=str, help="Compare with another park code")
    
    args = parser.parse_args()
    park_code = args.park_code.upper()
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║             PARK TRAIL DATA DEBUG TOOL                               ║
║  Park: {park_code:<10}                                                    ║
║  Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}                                         ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    # Initialize clients
    nps_key = os.getenv("NPS_API_KEY")
    if not nps_key:
        print("❌ ERROR: NPS_API_KEY not found in environment")
        sys.exit(1)
    
    nps = NPSClient(api_key=nps_key)
    dm = DataManager()
    
    # ========================================
    # 1. Check Local Fixtures
    # ========================================
    divider("1. LOCAL FIXTURE STATUS")
    
    fixtures = check_local_fixtures(dm, park_code)
    print(f"{'File':<35} {'Status':<10} {'Count':<10}")
    print("-" * 55)
    for fname, info in fixtures.items():
        status = "✅ exists" if info["exists"] else "❌ missing"
        count = str(info["count"]) if info["count"] is not None else "-"
        print(f"{fname:<35} {status:<10} {count:<10}")
    
    # Highlight critical issues
    if not fixtures["places.json"]["exists"]:
        print("\n⚠️  WARNING: places.json is MISSING - this is critical for trail classification!")
    
    if fixtures["trails_v2.json"]["exists"] and fixtures["trails_v2.json"]["count"] == 0:
        print("\n⚠️  WARNING: trails_v2.json exists but is EMPTY!")
    
    # ========================================
    # 2. Fetch and Analyze NPS API Data
    # ========================================
    divider("2. NPS API DATA ANALYSIS")
    
    places_raw, things_raw = fetch_park_data(nps, park_code)
    
    places_stats = analyze_endpoint(places_raw, "places", args.verbose)
    things_stats = analyze_endpoint(things_raw, "thingstodo", args.verbose)
    
    print(f"\n📊 PLACES ENDPOINT:")
    print(f"   Total items: {places_stats['total']}")
    print(f"   Trail candidates: {places_stats['trail_candidates']}")
    print(f"   With 'Hiking' activity: {places_stats['with_hiking_activity']}")
    print(f"   With valid location: {places_stats['with_location']}")
    
    print(f"\n📊 THINGSTODO ENDPOINT:")
    print(f"   Total items: {things_stats['total']}")
    print(f"   Trail candidates: {things_stats['trail_candidates']}")
    print(f"   With 'Hiking' activity: {things_stats['with_hiking_activity']}")
    print(f"   With valid location: {things_stats['with_location']}")
    
    # ========================================
    # 3. Trail Candidates Detail
    # ========================================
    divider("3. TRAIL CANDIDATES")

    all_candidates = []
    
    print("From PLACES:")
    for item in places_stats["items"]:
        if item["would_classify_as_trail"]:
            all_candidates.append(item)
            print(f"  🥾 {item['title']}")
            if args.verbose:
                print(f"     Keywords: {item['hike_keywords_found']}")
                print(f"     Activities: {item['activities']}")
                print(f"     Has location: {item['has_location']}")
    
    if not any(i["would_classify_as_trail"] for i in places_stats["items"]):
        print("  (none)")
    
    print("\nFrom THINGSTODO:")
    for item in things_stats["items"]:
        if item["would_classify_as_trail"]:
            all_candidates.append(item)
            print(f"  🥾 {item['title']}")
            if args.verbose:
                print(f"     Keywords: {item['hike_keywords_found']}")
                print(f"     Activities: {item['activities']}")
                print(f"     Duration: {item['duration']}")
    
    if not any(i["would_classify_as_trail"] for i in things_stats["items"]):
        print("  (none)")
    
    print(f"\n📈 TOTAL TRAIL CANDIDATES: {len(all_candidates)}")
    
    # ========================================
    # 4. Items with Hiking Activity (but not classified as trail)
    # ========================================
    divider("4. HIKING ACTIVITY ITEMS NOT CLASSIFIED AS TRAILS")
    
    missed = []
    for item in places_stats["items"] + things_stats["items"]:
        if item["has_hiking_activity"] and not item["would_classify_as_trail"]:
            missed.append(item)
            print(f"  ⚠️  {item['title']}")
            print(f"      Reason not classified: {item['classification_reason']}")
            if args.verbose:
                print(f"      Description: {item['description_preview']}")
    
    if not missed:
        print("  (none - all hiking items are being classified)")
    
    # ========================================
    # 5. Comparison (if requested)
    # ========================================
    if args.compare:
        compare_code = args.compare.upper()
        divider(f"5. COMPARISON WITH {compare_code}")
        
        compare_places, compare_things = fetch_park_data(nps, compare_code)
        compare_places_stats = analyze_endpoint(compare_places, "places")
        compare_things_stats = analyze_endpoint(compare_things, "thingstodo")
        
        print(f"\n{'Metric':<35} {park_code:<15} {compare_code:<15}")
        print("-" * 65)
        print(f"{'Places - Total':<35} {places_stats['total']:<15} {compare_places_stats['total']:<15}")
        print(f"{'Places - Trail candidates':<35} {places_stats['trail_candidates']:<15} {compare_places_stats['trail_candidates']:<15}")
        print(f"{'Things - Total':<35} {things_stats['total']:<15} {compare_things_stats['total']:<15}")
        print(f"{'Things - Trail candidates':<35} {things_stats['trail_candidates']:<15} {compare_things_stats['trail_candidates']:<15}")
    
    # ========================================
    # 6. Save API Responses (if requested)
    # ========================================
    if args.save:
        divider("6. SAVING API RESPONSES")
        
        output_dir = f"data_samples/nps/raw/{park_code}"
        os.makedirs(output_dir, exist_ok=True)
        
        with open(f"{output_dir}/debug_places.json", "w") as f:
            json.dump(places_raw, f, indent=2)
        print(f"✅ Saved {output_dir}/debug_places.json")
        
        with open(f"{output_dir}/debug_thingstodo.json", "w") as f:
            json.dump(things_raw, f, indent=2)
        print(f"✅ Saved {output_dir}/debug_thingstodo.json")
    
    # ========================================
    # Summary
    # ========================================
    divider("SUMMARY", char="═")
    
    issues = []
    
    if not fixtures["places.json"]["exists"]:
        issues.append("❌ places.json is MISSING - run data fetch to get it")
    
    if fixtures["trails_v2.json"]["exists"] and fixtures["trails_v2.json"]["count"] == 0:
        issues.append("❌ trails_v2.json is EMPTY - check classification/enrichment")
    
    if places_stats["trail_candidates"] == 0 and things_stats["trail_candidates"] == 0:
        issues.append("❌ NO trail candidates found in API data - NPS data may be sparse for this park")
    
    if len(missed) > 0:
        issues.append(f"⚠️  {len(missed)} items have 'Hiking' activity but aren't classified as trails")
    
    if issues:
        print("Issues found:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✅ No obvious issues detected")
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                     DEBUG COMPLETE                                   ║
╚══════════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
