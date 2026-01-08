import os
import json
import requests
import time
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# --- Configuration ---
OUTPUT_DIR = "data_samples/ui_fixtures"

PARK_NAME_MAP = {
    "ZION": "Zion National Park",
    "YOSE": "Yosemite National Park",
    "GRCA": "Grand Canyon National Park",
    "BRCA": "Bryce Canyon National Park",
    "ARCH": "Arches National Park",
    "JOTR": "Joshua Tree National Park",
    "YELL": "Yellowstone National Park"
}


class PhotoSpot(BaseModel):
    rank: Optional[int] = None
    name: str
    parkCode: Optional[str] = None
    description: str
    best_time_of_day: List[str]
    tips: List[str]
    image_url: Optional[str] = None
    source_url: Optional[str] = None


class PhotoGuide(BaseModel):
    spots: List[PhotoSpot]


def _search_blogs(park_name: str, serper_key: str) -> List[str]:
    """Search for photography blog URLs using Serper API."""
    url = "https://google.serper.dev/search"
    payload = json.dumps({
        "q": f"best photography spots {park_name} guide blog",
        "gl": "us", "hl": "en",
        "num": 8
    })
    headers = {'X-API-KEY': serper_key, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        return [x['link'] for x in response.json().get("organic", [])]
    except Exception as e:
        raise ValueError(f"Blog search failed: {e}")


def fetch_photo_spots_for_park(park_code: str, progress_callback=None) -> List[Dict]:
    """
    Programmatic entry point for fetching photo spots for a single park.
    
    Args:
        park_code: The park code (e.g., "BRCA")
        progress_callback: Optional callback function(current, total, message)
        
    Returns:
        List of photo spot dictionaries
        
    Raises:
        ValueError: If API keys not found
    """
    from firecrawl import Firecrawl
    from google import genai
    
    park_code = park_code.upper()
    
    serper_key = os.getenv("SERPER_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
    
    if not all([serper_key, gemini_key, firecrawl_key]):
        missing = []
        if not serper_key: missing.append("SERPER_API_KEY")
        if not gemini_key: missing.append("GEMINI_API_KEY")
        if not firecrawl_key: missing.append("FIRECRAWL_API_KEY")
        raise ValueError(f"Missing API keys: {', '.join(missing)}")
    
    park_name = PARK_NAME_MAP.get(park_code, f"{park_code} National Park")
    
    if progress_callback:
        progress_callback(0, 5, f"Searching blogs for {park_name}...")
    
    urls = _search_blogs(park_name, serper_key)
    
    if not urls:
        raise ValueError(f"No blog sources found for {park_name}")
    
    app = Firecrawl(api_key=firecrawl_key)
    client = genai.Client(api_key=gemini_key)
    
    all_spots = []
    seen_names = set()
    
    for i, url in enumerate(urls[:5]):
        if len(all_spots) >= 25:
            break
        
        if progress_callback:
            progress_callback(i + 1, 5, f"Scraping: {url[:50]}...")
        
        try:
            res = app.scrape(url=url, formats=['markdown'])
            
            md = ""
            if isinstance(res, dict):
                md = res.get('markdown', "")
            elif hasattr(res, 'markdown'):
                md = res.markdown
            
            if md:
                prompt = f"""
                Analyze this blog post about photography in {park_name}.
                Extract a list of distinct photography spots.
                
                CRITICAL FOR IMAGES:
                Find the valid image URL (markdown syntax ![alt](url)) physically closest to the spot description.
                If no image is found, set null.

                For each spot, extract:
                1. Rank (1 for best, inferred from text/order)
                2. Name (exact location)
                3. Description (why it's good)
                4. Best Time of Day (e.g. ["Sunset", "Sunrise"])
                5. Tips (photography specific)
                6. Image URL

                Markdown Content (truncated):
                {md[:50000]}
                """
                
                response = client.models.generate_content(
                    model=gemini_model,
                    contents=prompt,
                    config={'response_mime_type': 'application/json', 'response_schema': PhotoGuide}
                )
                
                guide = response.parsed
                if guide and guide.spots:
                    for spot in guide.spots:
                        norm_name = spot.name.lower().replace("the ", "").strip()
                        if norm_name not in seen_names:
                            spot_data = spot.model_dump()
                            spot_data['parkCode'] = park_code.lower()
                            spot_data['source_url'] = url
                            all_spots.append(spot_data)
                            seen_names.add(norm_name)
        
        except Exception as e:
            # Log error but continue with other URLs
            pass
    
    # Sort by rank and re-index
    all_spots.sort(key=lambda x: x.get('rank') or 999)
    for i, spot in enumerate(all_spots):
        spot['rank'] = i + 1
    
    # Save to file
    if all_spots:
        output_path = f"{OUTPUT_DIR}/{park_code}/photo_spots.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(all_spots, f, indent=2)
    
    if progress_callback:
        progress_callback(5, 5, f"Found {len(all_spots)} photo spots")
    
    return all_spots


# --- Legacy CLI Interface ---
def fetch_and_extract_spots():
    """Legacy function for backward compatibility."""
    park_code = os.getenv("PARK_CODE", "ZION")
    
    def cli_progress(current, total, message):
        print(f"[{current}/{total}] {message}")
    
    try:
        spots = fetch_photo_spots_for_park(park_code, progress_callback=cli_progress)
        print(f"✅ Saved {len(spots)} photo spots")
    except ValueError as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    fetch_and_extract_spots()
