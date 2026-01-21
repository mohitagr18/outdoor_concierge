import os
import json
from app.config import SUPPORTED_PARKS

REQUIRED_FIXTURES = [
    "park_details.json",
    "campgrounds.json",
    "visitor_centers.json",
    "webcams.json",
    "things_to_do.json",
    "places.json",
]

EXPLORER_FIXTURES = [
    "trails_v2.json",
    "photo_spots.json",
    "scenic_drives.json",
]

def check_park_status(park_code):
    base_dir = f"data_samples/ui_fixtures/{park_code.upper()}"
    if not os.path.exists(base_dir):
        return "No Data", []

    existing_files = os.listdir(base_dir)
    
    missing_required = [f for f in REQUIRED_FIXTURES if f not in existing_files]
    missing_explorer = [f for f in EXPLORER_FIXTURES if f not in existing_files]
    
    if not missing_required and not missing_explorer:
        return "✅ Full Data", []
    
    if "park_details.json" not in existing_files:
         return "❌ No Data", missing_required + missing_explorer

    if missing_required:
        return "⚠️ Partial (Missing Required)", missing_required
        
    if missing_explorer:
        return "⚠️ Partial (Missing Explorer)", missing_explorer

    return "❓ Unknown", []

def main():
    print(f"{'PARK CODE':<10} {'PARK NAME':<40} {'STATUS':<30} {'MISSING'}")
    print("-" * 100)
    
    full_data_parks = []
    
    for code, name in sorted(SUPPORTED_PARKS.items()):
        status, missing = check_park_status(code)
        missing_str = ", ".join(missing) if missing else ""
        print(f"{code.upper():<10} {name[:38]:<40} {status:<30} {missing_str}")
        
        if status == "✅ Full Data":
            full_data_parks.append(f"{name} ({code.upper()})")

    print("\n" + "="*50)
    print(f"Total Full Data Parks: {len(full_data_parks)}")
    for p in full_data_parks:
        print(f" - {p}")

if __name__ == "__main__":
    main()
