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


class ScenicDrive(BaseModel):
    rank: Optional[int] = None
    name: str
    parkCode: Optional[str] = None
    description: str
    distance_miles: Optional[float] = None
    drive_time: Optional[str] = None  # e.g. "2-3 hours"
    highlights: List[str] = []  # Key viewpoints/stops
    best_time: Optional[str] = None  # e.g. "Sunrise", "Any time"
    tips: List[str] = []
    image_url: Optional[str] = None
    source_url: Optional[str] = None


class ScenicDriveGuide(BaseModel):
    drives: List[ScenicDrive]


def _search_blogs(park_name: str, serper_key: str) -> List[str]:
    """Search for scenic drive blog URLs using Serper API."""
    url = "https://google.serper.dev/search"
    payload = json.dumps({
        "q": f"best scenic drives {park_name} guide routes",
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


def fetch_scenic_drives_for_park(park_code: str, progress_callback=None) -> List[Dict]:
    """
    Fetch scenic drive data for a park by scraping travel blogs.
    
    Args:
        park_code: The park code (e.g., "BRCA")
        progress_callback: Optional callback function(current, total, message)
        
    Returns:
        List of scenic drive dictionaries
        
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
        progress_callback(0, 5, f"Searching scenic drive guides for {park_name}...")
    
    urls = _search_blogs(park_name, serper_key)
    
    if not urls:
        raise ValueError(f"No scenic drive sources found for {park_name}")
    
    app = Firecrawl(api_key=firecrawl_key)
    client = genai.Client(api_key=gemini_key)
    
    all_drives = []
    seen_names = set()
    raw_scraped_data = []  # Store raw scraped content
    
    # Create raw directory for saving scraped data
    raw_dir = f"data_samples/nps/raw/{park_code}"
    os.makedirs(raw_dir, exist_ok=True)
    
    for i, url in enumerate(urls[:5]):
        if len(all_drives) >= 15:
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
                # Store raw scraped content for later saving
                raw_scraped_data.append({
                    "url": url,
                    "markdown_length": len(md),
                    "markdown": md  # Full markdown content
                })
                
                prompt = f"""
                Analyze this blog post about scenic drives in {park_name}.
                Extract a list of distinct scenic drives/routes.
                
                CRITICAL - IMAGE EXTRACTION:
                - Look for ALL image URLs in the markdown content
                - Images appear as: ![alt text](https://...) or ![](https://...)
                - Also look for image URLs in HTML img tags: <img src="https://...">
                - For EACH drive, find the image URL that appears closest to that drive's description
                - Prefer high-quality images (look for keywords like headers, hero, featured)
                - If multiple images exist near a drive, pick the first one
                - DO NOT return null for image_url unless you truly cannot find ANY image in the content
                - Even a general scenic image from the page is better than null

                For each scenic drive, extract:
                1. Rank (1 for best, inferred from text/order)
                2. Name (exact route/road name, e.g. "Tioga Road", "Zion Canyon Scenic Drive")
                3. Description (what makes it scenic, what you'll see)
                4. Distance in miles (if mentioned)
                5. Drive time (e.g. "1-2 hours")
                6. Highlights (key viewpoints, overlooks, stops along the way)
                7. Best Time (e.g. "Sunrise", "Sunset", "Any time", "Summer only")
                8. Tips (driving specific - road conditions, closures, vehicle restrictions)
                9. Image URL - REQUIRED: Extract from markdown ![](url) or HTML img tags

                Focus on actual driving routes, not hiking trails or general park information.

                Markdown Content (truncated):
                {md[:50000]}
                """
                
                response = client.models.generate_content(
                    model=gemini_model,
                    contents=prompt,
                    config={'response_mime_type': 'application/json', 'response_schema': ScenicDriveGuide}
                )
                
                guide = response.parsed
                if guide and guide.drives:
                    for drive in guide.drives:
                        # Normalize name for deduplication
                        norm_name = drive.name.lower().replace("the ", "").strip()
                        # Remove parenthetical suffixes for comparison (e.g., "(Highway 120)")
                        base_name = norm_name.split("(")[0].strip()
                        # Also remove common suffixes like "road", "drive", "highway", "byway"
                        core_name = base_name.replace(" road", "").replace(" drive", "").replace(" highway", "").replace(" byway", "").replace(" scenic", "").strip()
                        
                        # Check for duplicates using multiple strategies
                        is_duplicate = False
                        for seen in seen_names:
                            seen_base = seen.split("(")[0].strip()
                            seen_core = seen_base.replace(" road", "").replace(" drive", "").replace(" highway", "").replace(" byway", "").replace(" scenic", "").strip()
                            
                            # Check if names are similar enough to be duplicates
                            if (norm_name == seen or 
                                base_name == seen_base or 
                                core_name == seen_core or
                                core_name in seen or 
                                seen_core in core_name or
                                (len(core_name) > 3 and len(seen_core) > 3 and 
                                 (core_name.startswith(seen_core) or seen_core.startswith(core_name)))):
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            drive_data = drive.model_dump()
                            drive_data['parkCode'] = park_code.lower()
                            drive_data['source_url'] = url
                            all_drives.append(drive_data)
                            seen_names.add(norm_name)
        
        except Exception as e:
            # Log error but continue with other URLs
            pass
    
    # Save raw scraped data to nps/raw directory
    if raw_scraped_data:
        raw_output_path = os.path.join(raw_dir, "raw_scenic_drives.json")
        with open(raw_output_path, "w") as f:
            json.dump(raw_scraped_data, f, indent=2)
    
    # Sort by rank and re-index
    all_drives.sort(key=lambda x: x.get('rank') or 999)
    for i, drive in enumerate(all_drives):
        drive['rank'] = i + 1
    
    # Save to file
    if all_drives:
        output_path = f"{OUTPUT_DIR}/{park_code}/scenic_drives.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(all_drives, f, indent=2)
    
    if progress_callback:
        progress_callback(5, 5, f"Found {len(all_drives)} scenic drives")
    
    return all_drives


# --- CLI Interface ---
def fetch_drives_cli():
    """CLI entry point for fetching scenic drives."""
    park_code = os.getenv("PARK_CODE", "ZION")
    
    def cli_progress(current, total, message):
        print(f"[{current}/{total}] {message}")
    
    try:
        drives = fetch_scenic_drives_for_park(park_code, progress_callback=cli_progress)
        print(f"✅ Saved {len(drives)} scenic drives")
    except ValueError as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    fetch_drives_cli()
