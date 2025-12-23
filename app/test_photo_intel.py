import os
import json
import requests
from dotenv import load_dotenv
from firecrawl import Firecrawl
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI

load_dotenv()
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

class PhotoSpot(BaseModel):
    name: str
    best_time: str # e.g. "Sunset", "Sunrise"
    tips: str

class PhotoGuide(BaseModel):
    spots: List[PhotoSpot]

def search_blogs(park="Zion National Park"):
    print(f"Searching blogs for: {park} photography...")
    url = "https://google.serper.dev/search"
    payload = json.dumps({
        "q": f"best photography spots {park} guide blog",
        "gl": "us", "hl": "en"
    })
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        data = requests.post(url, headers=headers, data=payload).json()
        return [x['link'] for x in data.get("organic", [])[:2]]
    except: return []

def main():
    if not SERPER_API_KEY: 
        print("Missing SERPER_API_KEY")
        return
        
    urls = search_blogs()
    app = Firecrawl(api_key=FIRECRAWL_API_KEY)
    client = OpenAI(api_key=OPENAI_API_KEY)

    print(f"\n--- Scraping Photography Blogs ---\n")
    for url in urls:
        print(f"Scraping: {url}")
        try:
            res = app.scrape(url=url, formats=['markdown'])
            md = res.get('markdown') if isinstance(res, dict) else str(res)
            
            if md:
                completion = client.beta.chat.completions.parse(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Extract photography spots, best times, and specific tips."},
                        {"role": "user", "content": md[:30000]}
                    ],
                    response_format=PhotoGuide,
                )
                guide = completion.choices[0].message.parsed
                
                print(f"\nSOURCE: {url}")
                for spot in guide.spots:
                    print(f"📸 {spot.name}")
                    print(f"   Time: {spot.best_time}")
                    print(f"   Tip: {spot.tips}")
                print("-" * 30)
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    main()
