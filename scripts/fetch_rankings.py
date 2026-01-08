import os
import json
import time
import re
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Helpers
def _normalize_time_string(s: str) -> str:
    if not s:
        return s
    # replace en/em dashes with ASCII hyphen
    s = s.replace('\u2013', '-').replace('\u2014', '-').replace('–', '-').replace('—', '-')
    # normalize whitespace
    s = re.sub(r"\s+", ' ', s).strip()
    return s


# --- Configuration ---
OUTPUT_DIR = "data_samples/ui_fixtures"

# Map Park Code to AllTrails URL segments
# URL Format: https://www.alltrails.com/parks/us/{state}/{park-slug}/hiking
PARK_URL_MAP = {
    "ZION": "utah/zion-national-park",
    "YOSE": "california/yosemite-national-park",
    "GRCA": "arizona/grand-canyon-national-park",
    "BRCA": "utah/bryce-canyon-national-park",
}


def scrape_rankings_for_park(park_code: str, progress_callback=None) -> List[Dict]:
    """
    Programmatic entry point for scraping AllTrails rankings for a single park.
    
    Args:
        park_code: The park code (e.g., "BRCA")
        progress_callback: Optional callback function(current, total, message)
        
    Returns:
        List of trail ranking dictionaries
        
    Raises:
        ValueError: If API keys not found or park code unsupported
    """
    from firecrawl import Firecrawl
    from google import genai
    from pydantic import BaseModel
    
    park_code = park_code.upper()
    
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not firecrawl_key:
        raise ValueError("FIRECRAWL_API_KEY not found in environment")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY not found in environment")
    
    if park_code not in PARK_URL_MAP:
        raise ValueError(f"Unsupported park code: {park_code}. Supported: {list(PARK_URL_MAP.keys())}")
    
    slug = PARK_URL_MAP[park_code]
    target_url = f"https://www.alltrails.com/parks/us/{slug}/hiking"
    
    if progress_callback:
        progress_callback(0, 3, f"Scraping AllTrails for {park_code}...")
    
    app = Firecrawl(api_key=firecrawl_key)
    
    try:
        if progress_callback:
            progress_callback(1, 3, "Fetching page content...")
        
        scraped_data = app.scrape(url=target_url, formats=['markdown'])
        markdown = scraped_data.markdown if hasattr(scraped_data, 'markdown') else ''
        
        if not markdown:
            raise ValueError("No markdown content returned from scrape")
        
        if progress_callback:
            progress_callback(2, 3, f"Parsing {len(markdown)} chars with Gemini...")
        
        client = genai.Client(api_key=gemini_key)
        
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

            # Save raw rankings
            output_path = f"{OUTPUT_DIR}/{park_code}/rankings.json"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(rankings, f, indent=2)
            
            if progress_callback:
                progress_callback(3, 3, f"Extracted {len(rankings)} trail rankings")
            
            return rankings
        else:
            raise ValueError("LLM extraction failed - no parsed response")

    except Exception as e:
        raise ValueError(f"Error scraping rankings: {e}")


def merge_rankings_for_park(park_code: str, rankings: List[Dict], progress_callback=None) -> int:
    """
    Merges AllTrails rankings with existing trails_v2.json for a park.
    
    Args:
        park_code: The park code (e.g., "BRCA")
        rankings: List of ranking dictionaries from scrape_rankings_for_park
        progress_callback: Optional callback function(current, total, message)
        
    Returns:
        Number of trails merged
        
    Raises:
        FileNotFoundError: If trails_v2.json doesn't exist
    """
    park_code = park_code.upper()
    
    if not rankings:
        return 0
    
    trails_file = f"{OUTPUT_DIR}/{park_code}/trails_v2.json"
    if not os.path.exists(trails_file):
        raise FileNotFoundError(f"{trails_file} not found. Run trail enrichment first.")
    
    with open(trails_file, "r") as f:
        local_trails = json.load(f)
    
    # Cleanup legacy tags and normalize time strings
    for t in local_trails:
        for bad_key in ("source", "difficulty_source", "length_miles_source", "estimated_time_hours_source"):
            if bad_key in t:
                del t[bad_key]
        if t.get('estimated_time_hours'):
            t['estimated_time_hours'] = _normalize_time_string(t.get('estimated_time_hours'))
        if t.get('alltrails_estimated_time_hours'):
            t['alltrails_estimated_time_hours'] = _normalize_time_string(t.get('alltrails_estimated_time_hours'))
    
    if progress_callback:
        progress_callback(0, len(rankings), "Merging rankings with local data...")
    
    def norm(name):
        n = name.lower()
        n = n.replace(" trailhead", "").replace(" trail", "")
        n = n.replace(" falls", " fall").replace(" via ", " ")
        n = re.sub(r'[^a-z0-9]', '', n)
        return n
    
    ranked_map = {}
    for t in rankings:
        norm_name = norm(t['name'])
        if norm_name not in ranked_map or t['rank'] < ranked_map[norm_name]['rank']:
            ranked_map[norm_name] = t
    
    merged_count = 0
    appended_count = 0
    used_keys = set()
    
    for trail in local_trails:
        local_name = norm(trail['name'])
        
        match = None
        matched_key = None
        
        if local_name in ranked_map:
            match = ranked_map[local_name]
            matched_key = local_name
        else:
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
            if matched_key:
                used_keys.add(matched_key)
    
    # Append unmatched AllTrails-only rankings as minimal trail records
    for r_name, r_data in ranked_map.items():
        if r_name in used_keys:
            continue
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
        if new_trail.get('elevation_gain_ft'):
            new_trail['elevation_gain_ft_source'] = 'alltrails'
        local_trails.append(new_trail)
        appended_count += 1
    
    with open(trails_file, "w") as f:
        json.dump(local_trails, f, indent=2)
    
    if progress_callback:
        progress_callback(merged_count + appended_count, merged_count + appended_count, 
                         f"Merged {merged_count}, appended {appended_count} trails")
    
    return merged_count + appended_count


def fetch_and_merge_rankings(park_code: str, progress_callback=None) -> int:
    """
    Convenience function: scrape rankings and merge in one call.
    
    Args:
        park_code: The park code (e.g., "BRCA")
        progress_callback: Optional callback function(current, total, message)
        
    Returns:
        Number of trails affected
    """
    rankings = scrape_rankings_for_park(park_code, progress_callback)
    return merge_rankings_for_park(park_code, rankings, progress_callback)


# --- Legacy CLI Interface ---
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
PARK_CODE = os.getenv("PARK_CODE", "ZION")

def scrape_rankings():
    """Legacy function for backward compatibility."""
    try:
        return scrape_rankings_for_park(PARK_CODE)
    except ValueError as e:
        print(f"Error: {e}")
        return []

def merge_rankings(rankings):
    """Legacy function for backward compatibility."""
    try:
        merge_rankings_for_park(PARK_CODE, rankings)
    except FileNotFoundError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    park_code = os.getenv("PARK_CODE", "ZION")
    
    def cli_progress(current, total, message):
        print(f"[{current}/{total}] {message}")
    
    try:
        print(f"🚀 Fetching AllTrails rankings for {park_code}...")
        count = fetch_and_merge_rankings(park_code, progress_callback=cli_progress)
        print(f"✅ Done! Affected {count} trails.")
    except ValueError as e:
        print(f"Error: {e}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
