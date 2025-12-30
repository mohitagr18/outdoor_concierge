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
PARK_CODE = os.getenv("PARK_CODE", "ZION") # Default to ZION

# Map Park Code to Full Name for better search results
PARK_NAME_MAP = {
    "ZION": "Zion National Park",
    "YOSE": "Yosemite National Park",
    "GRCA": "Grand Canyon National Park",
    "ARCH": "Arches National Park",
    "JOTR": "Joshua Tree National Park",
    "ACAD": "Acadia National Park",
    "BIBE": "Big Bend National Park",
    "GLAC": "Glacier National Park",
    "GRTE": "Grand Teton National Park",
    "ROMO": "Rocky Mountain National Park",
    "OLYM": "Olympic National Park",
    "YELL": "Yellowstone National Park"
}

class PhotoSpot(BaseModel):
    name: str
    parkCode: Optional[str] = None
    description: str
    best_time_of_day: List[str] # e.g. ["Sunset", "Sunrise"]
    tips: List[str]      # Specific photography advice
    image_url: Optional[str] = None

class PhotoGuide(BaseModel):
    spots: List[PhotoSpot]

def search_blogs(park_name):
    """
    Search for photography blog posts using Serper.
    """
    print(f"🔎 Searching blogs for: {park_name} photography...")
    url = "https://google.serper.dev/search"
    payload = json.dumps({
        "q": f"best photography spots {park_name} guide blog",
        "gl": "us", "hl": "en",
        "num": 5
    })
    headers = {
        'X-API-KEY': SERPER_API_KEY, 
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        data = response.json()
        
        # Get top 2-3 organic results
        links = [x['link'] for x in data.get("organic", [])[:3]]
        print(f"   Found {len(links)} potential sources.")
        return links
    except Exception as e:
        print(f"   Search failed: {e}")
        return []

def fetch_and_extract_spots():
    if not SERPER_API_KEY: 
        print("❌ Missing SERPER_API_KEY")
        return
    if not GEMINI_API_KEY:
        print("❌ Missing GEMINI_API_KEY")
        return
    if not FIRECRAWL_API_KEY:
        print("❌ Missing FIRECRAWL_API_KEY")
        return

    park_name = PARK_NAME_MAP.get(PARK_CODE, f"{PARK_CODE} National Park")
    urls = search_blogs(park_name)
    
    if not urls:
        print("❌ No sources found to scrape.")
        return

    app = Firecrawl(api_key=FIRECRAWL_API_KEY)
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    all_spots = []
    seen_names = set()

    print(f"\n🚀 Scraping & Analyzing Photo Spots for {park_name}...")

    # We only need one really good guide, but we'll try up to 2 until we get results
    for url in urls[:2]:
        print(f"   Scraping: {url}")
        try:
            res = app.scrape(url=url, formats=['markdown'])
            md = res.get('markdown') if isinstance(res, dict) else str(res)
            
            if md:
                print(f"   (Extracting with Gemini...)")
                prompt = f"""
                Extract the top 10 best photography spots from this blog post about {park_name}.
                For each spot, identify:
                1. Name (exact location name)
                2. Description (short summary of why it's a good spot)
                3. Best Time of Day (as a list, e.g. ["Sunrise", "Sunset", "Milky Way"])
                4. Specific Photography Tips (as a list of tips)
                
                Markdown Content (truncated):
                {md[:40000]}
                """
                
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config={'response_mime_type': 'application/json', 'response_schema': PhotoGuide}
                )
                
                guide = response.parsed
                if guide and guide.spots:
                    print(f"   ✅ Extracted {len(guide.spots)} spots from this source.")
                    
                    for spot in guide.spots:
                        # Simple deduplication by name
                        if spot.name.lower() not in seen_names:
                            spot_data = spot.model_dump()
                            spot_data['parkCode'] = PARK_CODE.lower()
                            all_spots.append(spot_data)
                            seen_names.add(spot.name.lower())
                    
                    # If we got a decent number of spots, we can stop
                    if len(all_spots) >= 8:
                        break
            else:
                 print("   ⚠️ No markdown content returned.")

        except Exception as e:
            print(f"   Failed to process {url}: {e}")

    # Save Results
    if all_spots:
        output_path = f"{OUTPUT_DIR}/{PARK_CODE}/photo_spots.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(all_spots, f, indent=2)
            
        print(f"\n💾 Saved {len(all_spots)} photo spots to {output_path}")
        
        # Preview
        print("\n--- Top Photo Spots ---")
        for s in all_spots[:5]:
            times = ", ".join(s.get('best_time_of_day', []))
            print(f"📸 {s['name']} ({times})")
    else:
        print("\n❌ Failed to extract any photo spots.")

if __name__ == "__main__":
    fetch_and_extract_spots()
