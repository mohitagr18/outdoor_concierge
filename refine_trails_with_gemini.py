import os
import json
import time
import re
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from google import genai

# Load environment variables
load_dotenv()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
PARK_CODE = "YOSE" # User can override this or we can loop
INPUT_FILE = f"data_samples/nps/raw/{PARK_CODE}/raw_trails.json"
OUTPUT_DIR = f"data_samples/ui_fixtures/{PARK_CODE}"
OUTPUT_FILE = f"{OUTPUT_DIR}/trails_v2.json"

# --- Models ---
class TrailStats(BaseModel):
    is_valid_hiking_trail: bool = Field(False, description="Set to True ONLY if this is clearly a hiking trail/route/walk. Set False for overlooks, shuttle stops, or buildings unless they are explicitly describing a hike starting there.")
    difficulty: Optional[str] = Field(None, description="Easy, Moderate, or Strenuous")
    length_miles: Optional[float] = Field(None, description="Total round-trip or point-to-point mileage")
    elevation_gain_ft: Optional[int] = Field(None, description="Total elevation gain in feet")
    route_type: Optional[str] = Field(None, description="Loop, Out & Back, or Point to Point")
    estimated_time_hours: Optional[str] = Field(None, description="Human readable time estimate, e.g. 3-4 hours")
    is_wheelchair_accessible: bool = Field(False, description="True if description mentions wheelchair access, paved path, or ADA accessible.")
    is_kid_friendly: bool = Field(False, description="True if description mentions kids, families, easy walk, or is short (< 2 miles) and flat.")

# --- Extraction Logic ---
def extract_trail_stats(trail_item: Dict[str, Any], client: genai.Client) -> Optional[TrailStats]:
    title = trail_item.get("title", "")
    
    # Normalize description from various NPS schemas (Places vs Things To Do)
    desc_parts = [
        trail_item.get("listingDescription") or "",
        trail_item.get("bodyText") or "",
        trail_item.get("shortDescription") or "",
        trail_item.get("longDescription") or "",
        trail_item.get("activityDescription") or "",
        trail_item.get("accessibilityInformation") or "" # CRITICAL: Include accessibility info
    ]
    desc_context = "\n".join([p for p in desc_parts if p.strip()])
    
    # Pre-Computation Heuristic:
    if len(desc_context) < 50:
        return None

    prompt = (
        f"You are a National Park expert. Analyze this place to see if it is a Hiking Trail.\n\n"
        f"Title: '{title}'\n"
        f"Description: {desc_context[:4000]}\n\n"
        "Instructions:\n"
        "1. DECIDE: Is this a hiking trail, route, or walking path? (True/False)\n"
        "2. IF TRUE, extract metrics:\n"
        "   - 'difficulty' (Easy, Moderate, Strenuous)\n"
        "   - 'length_miles' (numeric)\n"
        "   - 'elevation_gain_ft' (numeric)\n"
        "   - 'route_type'\n"
        "   - 'estimated_time_hours'\n"
        "   - 'is_wheelchair_accessible': Look for 'wheelchair', 'paved', 'accessible', 'ADA'.\n"
        "   - 'is_kid_friendly': Look for 'easy', 'family', 'kids', 'flat', 'short'.\n"
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={'response_mime_type': 'application/json', 'response_schema': TrailStats}
        )
        return response.parsed
    except Exception as e:
        print(f"Error extracting for {title}: {e}")
        return None

def main():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env")
        return
    
    # Allow overriding PARK_CODE via env var for quick testing
    park_code_env = os.getenv("PARK_CODE")
    global PARK_CODE, INPUT_FILE, OUTPUT_DIR, OUTPUT_FILE
    if park_code_env:
        PARK_CODE = park_code_env
        INPUT_FILE = f"data_samples/nps/raw/{PARK_CODE}/raw_trails.json"
        OUTPUT_DIR = f"data_samples/ui_fixtures/{PARK_CODE}"
        OUTPUT_FILE = f"{OUTPUT_DIR}/trails_v2.json"

    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file {INPUT_FILE} not found.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    client = genai.Client(api_key=GEMINI_API_KEY)

    with open(INPUT_FILE, "r") as f:
        # It's now the "raw_trails.json" (candidates) not just trailheads
        input_data = json.load(f)
        # Handle both list formats (raw_trails has {data:[], total:...} structure usually)
        if isinstance(input_data, dict) and "data" in input_data:
            trail_candidates = input_data["data"]
        else:
            trail_candidates = input_data

    results = []
    total = len(trail_candidates)
    print(f"🚀 Enriching {total} candidates for {PARK_CODE} using {GEMINI_MODEL}...")

    for i, trail in enumerate(trail_candidates):
        title = trail.get("title")
        print(f"[{i+1}/{total}] Processing: {title}...", end="", flush=True)
        
        stats = extract_trail_stats(trail, client)
        
        if stats and stats.is_valid_hiking_trail:
            # Merge original NPS data with enriched stats
            enriched_trail = {
                "id": trail.get("id"),
                "name": title,
                "description": trail.get("listingDescription") or title,
                "location": {
                    "lat": float(trail.get("latitude", 0) or 0),
                    "lon": float(trail.get("longitude", 0) or 0)
                },
                "images": trail.get("images", []),
                "nps_url": trail.get("url"),
                "difficulty": stats.difficulty,
                "length_miles": stats.length_miles,
                "elevation_gain_ft": stats.elevation_gain_ft,
                "route_type": stats.route_type,
                "estimated_time_hours": stats.estimated_time_hours,
                "is_wheelchair_accessible": stats.is_wheelchair_accessible,
                "is_kid_friendly": stats.is_kid_friendly,
                "last_enriched": datetime.now().isoformat()
            }
            results.append(enriched_trail)
            print(" ✅ Valid Trail")
        else:
            print(" ⏭️  Skipped (Not a trail)")
        
        # Pacing
        time.sleep(0.5)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✨ Enrichment Complete. Found {len(results)} Valid Trails out of {total} candidates.")
    print(f"📂 Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
