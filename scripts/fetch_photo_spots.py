import os
import json
import requests
import time
from dotenv import load_dotenv
from firecrawl import Firecrawl
from google import genai
from pydantic import BaseModel
from typing import List, Optional

# Load environment variables
load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

OUTPUT_DIR = "data_samples/ui_fixtures"
PARK_CODE = os.getenv("PARK_CODE", "ZION") 

PARK_NAME_MAP = {
    "ZION": "Zion National Park",
    "YOSE": "Yosemite National Park",
    "GRCA": "Grand Canyon National Park",
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
    source_url: Optional[str] = None  # <--- Added field

class PhotoGuide(BaseModel):
    spots: List[PhotoSpot]

def search_blogs(park_name):
    print(f"🔎 Searching blogs for: {park_name} photography...")
    url = "https://google.serper.dev/search"
    payload = json.dumps({
        "q": f"best photography spots {park_name} guide blog",
        "gl": "us", "hl": "en",
        "num": 8
    })
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        return [x['link'] for x in response.json().get("organic", [])]
    except Exception as e:
        print(f"   Search failed: {e}")
        return []

def fetch_and_extract_spots():
    if not all([SERPER_API_KEY, GEMINI_API_KEY, FIRECRAWL_API_KEY]):
        print("❌ Missing API Keys")
        return

    park_name = PARK_NAME_MAP.get(PARK_CODE, f"{PARK_CODE} National Park")
    urls = search_blogs(park_name)
    
    if not urls:
        print("❌ No sources found.")
        return

    app = Firecrawl(api_key=FIRECRAWL_API_KEY)
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    all_spots = []
    seen_names = set()

    print(f"\n🚀 Scraping Photo Spots for {park_name} (Target: 25)...")

    for url in urls[:5]:
        if len(all_spots) >= 25:
            break
            
        print(f"   Scraping: {url}")
        try:
            res = app.scrape(url=url, formats=['markdown'])
            
            # Handle Firecrawl response types
            md = ""
            if isinstance(res, dict):
                md = res.get('markdown', "")
            elif isinstance(res, list) and len(res) > 0:
                item = res[0]
                md = getattr(item, 'markdown', "") or (item.get('markdown', "") if isinstance(item, dict) else "")
            elif hasattr(res, 'markdown'):
                 md = res.markdown
            
            if md:
                print(f"   (Extracting with Gemini...)")
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
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config={'response_mime_type': 'application/json', 'response_schema': PhotoGuide}
                )
                
                guide = response.parsed
                if guide and guide.spots:
                    new_count = 0
                    for spot in guide.spots:
                        norm_name = spot.name.lower().replace("the ", "").strip()
                        if norm_name not in seen_names:
                            spot_data = spot.model_dump()
                            spot_data['parkCode'] = PARK_CODE.lower()
                            spot_data['source_url'] = url  # <--- Capture source URL
                            all_spots.append(spot_data)
                            seen_names.add(norm_name)
                            new_count += 1
                    
                    print(f"   ✅ Added {new_count} new spots")
            
        except Exception as e:
            print(f"   Failed to process {url}: {e}")

    # Sort by Rank and Re-index
    # Trust extracted rank first, then discovery order
    all_spots.sort(key=lambda x: x.get('rank') or 999)
    
    # Normalize ranks 1..N
    for i, spot in enumerate(all_spots):
        spot['rank'] = i + 1

    if all_spots:
        output_path = f"{OUTPUT_DIR}/{PARK_CODE}/photo_spots.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(all_spots, f, indent=2)
        print(f"\n💾 Saved {len(all_spots)} ranked photo spots to {output_path}")
    else:
        print("\n❌ Failed to extract any photo spots.")

if __name__ == "__main__":
    fetch_and_extract_spots()
