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
    is_pet_friendly: bool = Field(False, description="True if pets are allowed on the trail (including leashed pets). Look for 'pets allowed', 'dogs allowed', 'leashed pets', or similar. False if description explicitly says 'no pets' or 'pets not allowed'.")
    clean_description: Optional[str] = Field(None, description="A concise, 1-2 sentence description of the actual hike. Exclude hours, rules, regulations, getting there, accessibility info, and HTML. Focus only on what makes this trail unique and what you'll see/do.")

# --- Helpers: cleaning HTML / truncation
def strip_html_and_truncate(text: Optional[str], max_sentences: int = 2) -> Optional[str]:
    if not text:
        return None
    # Remove HTML tags
    cleaned = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    # Split into sentences (naive)
    parts = re.split(r'(?<=[.!?])\s+', cleaned)
    if len(parts) <= max_sentences:
        return cleaned
    return ' '.join(parts[:max_sentences]).strip()

# --- Helper: Infer Difficulty from Metrics ---
def infer_difficulty_from_metrics(length_miles: Optional[float], elevation_gain_ft: Optional[int], time_hours: Optional[str]) -> Optional[str]:
    """
    Infers difficulty level from trail metrics when explicit difficulty is missing.
    Uses empirical hiking standards:
    - Easy: < 3 miles, < 300 ft elevation, < 2 hours
    - Moderate: 3-8 miles, 300-1000 ft elevation, 2-5 hours
    - Strenuous: > 8 miles, > 1000 ft elevation, > 5 hours
    """
    if length_miles is None and elevation_gain_ft is None and time_hours is None:
        return None
    
    score = 0
    max_score = 0
    
    # Score based on length
    if length_miles is not None:
        max_score += 3
        if length_miles <= 3:
            score += 1
        elif length_miles <= 8:
            score += 2
        else:
            score += 3
    
    # Score based on elevation gain
    if elevation_gain_ft is not None:
        max_score += 3
        if elevation_gain_ft <= 300:
            score += 1
        elif elevation_gain_ft <= 1000:
            score += 2
        else:
            score += 3
    
    # Score based on time estimate
    if time_hours is not None:
        max_score += 3
        # Parse time estimate (e.g., "3-4 hours" or "2 hours")
        import re
        time_match = re.search(r'(\d+(?:\.\d+)?)', time_hours)
        if time_match:
            hours = float(time_match.group(1))
            if hours <= 2:
                score += 1
            elif hours <= 5:
                score += 2
            else:
                score += 3
    
    if max_score == 0:
        return None
    
    avg_score = score / max_score
    
    if avg_score <= 1.5:
        return "Easy"
    elif avg_score <= 2.2:
        return "Moderate"
    else:
        return "Strenuous"

# --- Extraction Logic ---
def extract_trail_stats(trail_item: Dict[str, Any], client: genai.Client) -> Optional[TrailStats]:
    title = trail_item.get("title", "")
    
    # Normalize description from various NPS schemas (Places vs Things To Do)
    desc_parts = [
        strip_html_and_truncate(trail_item.get("listingDescription") or "") or "",
        strip_html_and_truncate(trail_item.get("bodyText") or "") or "",
        strip_html_and_truncate(trail_item.get("shortDescription") or "") or "",
        strip_html_and_truncate(trail_item.get("longDescription") or "") or "",
        strip_html_and_truncate(trail_item.get("activityDescription") or "") or "",
        strip_html_and_truncate(trail_item.get("accessibilityInformation") or "") or "" # CRITICAL: Include accessibility info
    ]
    desc_context = "\n".join([p for p in desc_parts if p.strip()])
    
    # Add amenities information for pet detection
    amenities = trail_item.get("amenities", [])
    amenities_text = ", ".join(amenities) if amenities else ""
    if amenities_text:
        desc_context += f"\n\nAmenities: {amenities_text}"
    
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
        "   - 'difficulty' (Easy, Moderate, or Strenuous; can be null if not explicitly stated)\n"
        "   - 'length_miles' (numeric)\n"
        "   - 'elevation_gain_ft' (numeric)\n"
        "   - 'route_type'\n"
        "   - 'estimated_time_hours'\n"
        "   - 'is_wheelchair_accessible': Look for 'wheelchair', 'paved', 'accessible', 'ADA'.\n"
        "   - 'is_kid_friendly': Look for 'easy', 'family', 'kids', 'flat', 'short'.\n"
        "   - 'is_pet_friendly': Look for 'pets allowed', 'dogs allowed', 'leashed pets', or 'Pets Allowed' in amenities. Set False if description says 'pets not allowed' or 'no pets' or 'no dogs'.\n"
        "   - 'clean_description': Write a concise, 1-2 sentence description of the hike itself. Focus on what makes it unique and what hikers will see/do. EXCLUDE: hours of operation, rules/regulations, how to get there, accessibility requirements, parking info, permit requirements, HTML tags, and extra sections.\n"
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={'response_mime_type': 'application/json', 'response_schema': TrailStats}
        )
        stats = response.parsed
        
        # If Gemini didn't extract difficulty but we have metrics, infer it
        if stats and stats.is_valid_hiking_trail and stats.difficulty is None:
            inferred = infer_difficulty_from_metrics(
                stats.length_miles,
                stats.elevation_gain_ft,
                stats.estimated_time_hours
            )
            if inferred:
                stats.difficulty = inferred

        # If LLM didn't provide a clean_description, try to use cleaned listing/body text as fallback
        if stats and not stats.clean_description:
            candidate = strip_html_and_truncate(trail_item.get('listingDescription') or trail_item.get('bodyText') or '')
            if candidate and len(candidate) > 30:
                stats.clean_description = candidate
        
        # Post-process: Check amenities for pet-related info if LLM result is ambiguous
        if stats and stats.is_valid_hiking_trail:
            amenities = trail_item.get("amenities", [])
            amenities_str = " ".join(amenities).lower()
            if "pets allowed" in amenities_str:
                stats.is_pet_friendly = True
            elif "pets not allowed" in amenities_str or "no pets" in amenities_str:
                stats.is_pet_friendly = False
        
        return stats
    except Exception as e:
        print(f"Error extracting for {title}: {e}")
        return None

def refine_trails(park_code: str, progress_callback=None) -> List[Dict]:
    """
    Programmatic entry point for trail refinement.
    
    Args:
        park_code: The park code (e.g., "BRCA")
        progress_callback: Optional callback function(current, total, message) for progress updates
        
    Returns:
        List of enriched trail dictionaries
        
    Raises:
        ValueError: If GEMINI_API_KEY not found
        FileNotFoundError: If input raw_trails.json doesn't exist
    """
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
    
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment")
    
    input_file = f"data_samples/nps/raw/{park_code.upper()}/raw_trails.json"
    output_dir = f"data_samples/ui_fixtures/{park_code.upper()}"
    output_file = f"{output_dir}/trails_v2.json"
    
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file {input_file} not found")
    
    os.makedirs(output_dir, exist_ok=True)
    client = genai.Client(api_key=api_key)
    
    with open(input_file, "r") as f:
        input_data = json.load(f)
        if isinstance(input_data, dict) and "data" in input_data:
            trail_candidates = input_data["data"]
        else:
            trail_candidates = input_data
    
    results = []
    total = len(trail_candidates)
    
    if progress_callback:
        progress_callback(0, total, f"Starting enrichment of {total} trail candidates...")
    
    for i, trail in enumerate(trail_candidates):
        title = trail.get("title", "Unknown")
        
        if progress_callback:
            progress_callback(i, total, f"Processing: {title}")
        
        stats = extract_trail_stats(trail, client)
        
        if stats and stats.is_valid_hiking_trail:
            enriched_trail = {
                "id": trail.get("id"),
                "name": title,
                "description": stats.clean_description or strip_html_and_truncate(trail.get("listingDescription") or trail.get("bodyText")) or title,
                "location": {
                    # Handle both formats: location.lat/lon OR direct latitude/longitude fields
                    "lat": float(trail.get("location", {}).get("lat", 0) or trail.get("latitude", 0) or 0),
                    "lon": float(trail.get("location", {}).get("lon", 0) or trail.get("longitude", 0) or 0)
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
                "is_pet_friendly": stats.is_pet_friendly,
                "raw_listing_description": strip_html_and_truncate(trail.get("listingDescription")),
                "raw_body_text": strip_html_and_truncate(trail.get("bodyText")),
                "last_enriched": datetime.now().isoformat()
            }
            results.append(enriched_trail)
        
        # Pacing to avoid rate limits
        time.sleep(0.5)
    
    # Deduplicate trails with similar names (e.g., "X Trail" vs "X Trailhead")
    results = deduplicate_trails(results)
    
    # Save results
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    if progress_callback:
        progress_callback(total, total, f"Completed. Found {len(results)} valid trails.")
    
    return results


def deduplicate_trails(trails: List[Dict]) -> List[Dict]:
    """
    Deduplicates trails with similar names (e.g., "X Trail" vs "X Trailhead").
    Also removes promotional program entries (e.g., "X Hike the Hoodoos").
    Keeps the entry with more complete data.
    """
    from collections import defaultdict
    
    def normalize_name(name: str) -> str:
        """Normalize trail name for comparison."""
        name = name.lower()
        # Standardize common variants
        name = name.replace('peek-a-boo', 'peekaboo')
        # Remove promotional and common suffixes (order matters - longest first)
        for suffix in [' hike the hoodoos', ' trailhead', ' trail', ' hike', ' path']:
            name = name.replace(suffix, '')
        # Remove special chars and extra spaces
        name = name.replace("'", '').replace('-', ' ')
        name = re.sub(r'\s+', ' ', name).strip()
        return name
    
    def score_trail(t: Dict) -> int:
        """Score trail completeness - higher is better."""
        score = 0
        if t.get('length_miles'): score += 10
        if t.get('elevation_gain_ft'): score += 10
        if t.get('difficulty'): score += 5
        if t.get('description') and len(t.get('description', '')) > 50: score += 5
        if t.get('location', {}).get('lat', 0) != 0: score += 10
        if t.get('rating'): score += 5
        if t.get('review_count'): score += 5
        # Prefer non-promotional names
        if 'hike the hoodoos' not in t.get('name', '').lower(): score += 10
        if 'trailhead' not in t.get('name', '').lower(): score += 3
        return score
    
    # Normalize difficulty values (Hard -> Strenuous)
    for trail in trails:
        if trail.get('difficulty') == 'Hard':
            trail['difficulty'] = 'Strenuous'
    
    # Group by normalized name
    groups = defaultdict(list)
    for trail in trails:
        norm = normalize_name(trail.get('name', ''))
        groups[norm].append(trail)
    
    # For each group, keep the best one
    deduped = []
    for norm_name, group in groups.items():
        if len(group) == 1:
            deduped.append(group[0])
        else:
            # Sort by score descending, keep best
            group.sort(key=score_trail, reverse=True)
            best = group[0]
            
            # Merge data from duplicates into best
            for other in group[1:]:
                # Use other's data if best is missing it
                if not best.get('length_miles') and other.get('length_miles'):
                    best['length_miles'] = other['length_miles']
                if not best.get('elevation_gain_ft') and other.get('elevation_gain_ft'):
                    best['elevation_gain_ft'] = other['elevation_gain_ft']
                if not best.get('difficulty') and other.get('difficulty'):
                    best['difficulty'] = other['difficulty']
                if best.get('location', {}).get('lat', 0) == 0 and other.get('location', {}).get('lat', 0) != 0:
                    best['location'] = other['location']
            
            deduped.append(best)
    
    # Filter out standalone promotional program entries
    promotional_only = ['hike the hoodoos', 'scavenger hunt']
    deduped = [t for t in deduped if t.get('name', '').lower() not in promotional_only]
    
    return deduped


def main():
    """CLI entry point for manual execution."""
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env")
        return
    
    # Allow overriding PARK_CODE via env var for quick testing
    park_code = os.getenv("PARK_CODE", PARK_CODE)
    
    def cli_progress(current, total, message):
        if current == 0:
            print(f"🚀 {message}")
        elif current < total:
            print(f"[{current+1}/{total}] {message}...", end="", flush=True)
        else:
            print(f"\n✨ {message}")
    
    try:
        results = refine_trails(park_code, progress_callback=cli_progress)
        print(f"📂 Saved {len(results)} trails to data_samples/ui_fixtures/{park_code.upper()}/trails_v2.json")
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ValueError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

