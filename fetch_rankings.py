import os
import json
import time
import re
import uuid
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import Firecrawl

# Helpers
def _normalize_time_string(s: str) -> str:
    if not s:
        return s
    # replace en/em dashes with ASCII hyphen
    s = s.replace('\u2013', '-').replace('\u2014', '-').replace('–', '-').replace('—', '-')
    # normalize whitespace
    s = re.sub(r"\s+", ' ', s).strip()
    return s

# Load environment variables
load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
OUTPUT_DIR = "data_samples/ui_fixtures"

# Configuration
PARK_CODE = os.getenv("PARK_CODE", "ZION") # Default to ZION if not set

# Map Park Code to AllTrails URL segments
# URL Format: https://www.alltrails.com/parks/us/{state}/{park-slug}/hiking
PARK_URL_MAP = {
    "ZION": "utah/zion-national-park",
    "YOSE": "california/yosemite-national-park",
    "GRCA": "arizona/grand-canyon-national-park"
}

if PARK_CODE not in PARK_URL_MAP:
    print(f"Error: Unsupported PARK_CODE {PARK_CODE}")
    exit(1)

slug = PARK_URL_MAP[PARK_CODE]
TARGET_URL = f"https://www.alltrails.com/parks/us/{slug}/hiking"

def scrape_rankings():
    if not FIRECRAWL_API_KEY:
        print("Error: FIRECRAWL_API_KEY not found.")
        return

    print(f"🚀 Scraping AllTrails Rankings for {PARK_CODE}...")
    app = Firecrawl(api_key=FIRECRAWL_API_KEY)
    
    # Strategy: Scrape Markdown -> Generic LLM Parse
    # This avoids SDK version issues with 'extract' param
    try:
        print("   (1/2) Scraping page content...")
        scraped_data = app.scrape(
            url=TARGET_URL,
            formats=['markdown']
        )
        # Fix: V2 returns Document object, access attribute directly
        markdown = scraped_data.markdown if hasattr(scraped_data, 'markdown') else ''
        if not markdown:
            print("❌ No markdown returned.")
            return []
            
        with open("debug_rankings.md", "w") as f:
            f.write(markdown)
        print("   (Debug) Saved markdown to debug_rankings.md")
            
        print(f"   (2/2) Parsing {len(markdown)} chars with Gemini...")
        
        # Use Gemini to extract the list
        from google import genai
        from pydantic import BaseModel
        from typing import List, Optional
        
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            print("Error: GEMINI_API_KEY not found.")
            return []
            
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        class TrailRank(BaseModel):
            rank: int
            name: str
            url: str
            difficulty: Optional[str] = None
            rating: Optional[float] = None
            review_count: Optional[int] = None
            length_miles: Optional[float] = None
            elevation_gain_ft: Optional[int] = None
            estimated_time_hours: Optional[str] = None
            reviews_url: Optional[str] = None

        class RankingList(BaseModel):
            trails: List[TrailRank]

        prompt = f"""
        You are a data extractor. 
        I need a combined list of ranked trails from this markdown.
        
        Source 1: The numbered 'Top Trails' (Usually 1-10). Keep their specific ranks.
        Source 2: The 'Points of interest' list (bullet points). Treat these as Ranks 11, 12, 13... in the order they appear.
        
        INSTRUCTIONS:
        1. Extract the Top 10 trails first.
        2. Then extract trails from 'Points of interest'.
        3. DEDUPLICATE: If a trail in 'Points of interest' was already in Top 10, SKIP IT. Do not list it twice.
        4. Continue numbering the unique 'Points of interest' trails starting from 11.
        
        For each trail, capture:
        - rank (integer)
        - name (exact name)
        - url (full absolute https://alltrails.com/trail/... or /poi/... link)
        - difficulty (e.g., "Easy", "Moderate", "Hard", "Very Hard")
        - length_miles (floating point number)
        - elevation_gain_ft (integer, feet of elevation gain)
        - reviews_url (URL to reviews page, append ?reviews=true or #reviews to the trail URL if available)
        
        Markdown Content (truncated):
        {markdown[:60000]}
        """
        
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL") or "gemini-1.5-flash",
            contents=prompt,
            config={'response_mime_type': 'application/json', 'response_schema': RankingList}
        )
        
        if response.parsed:
            rankings = [t.model_dump() for t in response.parsed.trails]

            # Fallback: try to extract missing elevation/time from the raw markdown
            for r in rankings:
                name = r.get('name', '')
                # only attempt if value is missing
                need_elev = r.get('elevation_gain_ft') is None
                need_time = not r.get('estimated_time_hours')
                if not (need_elev or need_time):
                    continue

                idx = markdown.lower().find(name.lower())
                if idx == -1:
                    continue
                start = max(0, idx - 400)
                snippet = markdown[start: idx + 400]

                if need_elev:
                    m = re.search(r"(\d{1,3}(?:,\d{3})?)\s*(?:ft|feet|ft\.)", snippet, re.IGNORECASE)
                    if m:
                        try:
                            r['elevation_gain_ft'] = int(m.group(1).replace(',', ''))
                        except Exception:
                            pass

                if need_time:
                    m2 = re.search(r"(\d+(?:\.\d+)?(?:[-–—]\d+(?:\.\d+)?)?)\s*(?:hours|hour|hrs|hr)", snippet, re.IGNORECASE)
                    if m2:
                        val = m2.group(0).strip()
                        r['estimated_time_hours'] = _normalize_time_string(val)

            print(f"✅ Extracted {len(rankings)} trails (with fallbacks applied).")
            # Save raw rankings
            output_path = f"{OUTPUT_DIR}/{PARK_CODE}/rankings.json"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(rankings, f, indent=2)
            print(f"📂 Saved to {output_path}")
            return rankings
        else:
            print("❌ LLM Extraction failed.")
            return []

    except Exception as e:
        print(f"Error scraping rankings: {e}")
        return []

def merge_rankings(rankings):
    if not rankings:
        return

    trails_file = f"{OUTPUT_DIR}/{PARK_CODE}/trails_v2.json"
    if not os.path.exists(trails_file):
        print(f"Error: {trails_file} not found. Run enrichment first.")
        return

    with open(trails_file, "r") as f:
        local_trails = json.load(f)

    # Cleanup any legacy source tags we no longer want and normalize time strings
    for t in local_trails:
        for bad_key in ("source", "difficulty_source", "length_miles_source", "estimated_time_hours_source"):
            if bad_key in t:
                del t[bad_key]
        if t.get('estimated_time_hours'):
            t['estimated_time_hours'] = _normalize_time_string(t.get('estimated_time_hours'))
        if t.get('alltrails_estimated_time_hours'):
            t['alltrails_estimated_time_hours'] = _normalize_time_string(t.get('alltrails_estimated_time_hours'))

    print("\n🔗 Merging Rankings with Local Data...")
    
    def norm(name):
        n = name.lower()
        n = n.replace(" trailhead", "").replace(" trail", "")
        n = n.replace(" falls", " fall").replace(" via ", " ")
        n = re.sub(r'[^a-z0-9]', '', n) # Remove all non-alphanumeric
        return n

    # Create valid lookup maps
    # Metric: Normalized Lowercase Name
    ranked_map = {}
    for t in rankings:
        norm_name = norm(t['name'])
        # If collision, keep the better (lower) rank
        if norm_name not in ranked_map or t['rank'] < ranked_map[norm_name]['rank']:
            ranked_map[norm_name] = t
    
    merged_count = 0
    appended_count = 0
    used_keys = set()
    for trail in local_trails:
        # Normalize local name
        local_name = norm(trail['name'])
        
        # 1. Exact/Fuzzy Match
        match = None
        matched_key = None
        
        # Direct lookup
        if local_name in ranked_map:
            match = ranked_map[local_name]
            matched_key = local_name
        else:
            # simple fuzzy check
            for r_name, r_data in ranked_map.items():
                if r_name in local_name or local_name in r_name:
                    match = r_data
                    matched_key = r_name
                    break
        
        if match:
            trail['popularity_rank'] = match.get('rank')
            trail['alltrails_url'] = match.get('url')
            trail['alltrails_rating'] = match.get('rating')
            trail['alltrails_review_count'] = match.get('review_count')
            trail['alltrails_difficulty'] = match.get('difficulty')
            trail['alltrails_length_miles'] = match.get('length_miles')
            trail['alltrails_elevation_gain_ft'] = match.get('elevation_gain_ft')
            trail['alltrails_estimated_time_hours'] = _normalize_time_string(match.get('estimated_time_hours')) if match.get('estimated_time_hours') else None
            trail['alltrails_reviews_url'] = match.get('reviews_url')
            
            # Fill in missing NPS data with AllTrails data
            if not trail.get('difficulty') and match.get('difficulty'):
                trail['difficulty'] = match.get('difficulty')
            
            if not trail.get('length_miles') and match.get('length_miles'):
                trail['length_miles'] = match.get('length_miles')
            
            if not trail.get('elevation_gain_ft') and match.get('elevation_gain_ft'):
                trail['elevation_gain_ft'] = match.get('elevation_gain_ft')
                trail['elevation_gain_ft_source'] = 'alltrails'

            if not trail.get('estimated_time_hours') and match.get('estimated_time_hours'):
                trail['estimated_time_hours'] = _normalize_time_string(match.get('estimated_time_hours'))
            
            merged_count += 1
            # mark ranking as used so we can append unmatched later
            if matched_key:
                used_keys.add(matched_key)
            print(f"   Matched: '{trail['name']}' -> '{match['name']}' (Rank #{match['rank']})")
        else:
            # print(f"   No Match: {trail['name']}")
            pass

    # Append unmatched AllTrails-only rankings as minimal trail records
    for r_name, r_data in ranked_map.items():
        if r_name in used_keys:
            continue
        # create a minimal trail entry
        new_trail = {
            "id": str(uuid.uuid4()),
            "name": r_data.get('name'),
            "description": r_data.get('name'),
            "location": {"lat": 0.0, "lon": 0.0},
            "images": [],
            "nps_url": None,
            "difficulty": r_data.get('difficulty'),
            "length_miles": r_data.get('length_miles'),
            "elevation_gain_ft": r_data.get('elevation_gain_ft'),
            "route_type": None,
            "estimated_time_hours": _normalize_time_string(r_data.get('estimated_time_hours')) if r_data.get('estimated_time_hours') else None,
            "is_wheelchair_accessible": False,
            "is_kid_friendly": False,
            "last_enriched": datetime.now().isoformat(),
            "popularity_rank": r_data.get('rank'),
            "alltrails_url": r_data.get('url'),
            "alltrails_rating": r_data.get('rating'),
            "alltrails_review_count": r_data.get('review_count'),
            "alltrails_difficulty": r_data.get('difficulty'),
            "alltrails_length_miles": r_data.get('length_miles'),
            "alltrails_elevation_gain_ft": r_data.get('elevation_gain_ft'),
            "alltrails_estimated_time_hours": _normalize_time_string(r_data.get('estimated_time_hours')) if r_data.get('estimated_time_hours') else None,
            "alltrails_reviews_url": r_data.get('reviews_url')
        }

        # tag primary fields' source when populated from AllTrails (only elevation kept)
        if new_trail.get('elevation_gain_ft'):
            new_trail['elevation_gain_ft_source'] = 'alltrails'

        local_trails.append(new_trail)
        appended_count += 1
        print(f"   Appended AllTrails-only trail: '{new_trail['name']}' (Rank #{new_trail.get('popularity_rank')})")

    with open(trails_file, "w") as f:
        json.dump(local_trails, f, indent=2)
    
    print(f"✨ Merge Complete. {merged_count}/{len(local_trails)} trails enriched with external intel.")

if __name__ == "__main__":
    rankings = scrape_rankings()
    merge_rankings(rankings)
