import os
import json
from dotenv import load_dotenv
from firecrawl import Firecrawl
from google import genai
from pydantic import BaseModel
from typing import List, Optional

# Load env vars
load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"

TARGET_URL = "https://www.alltrails.com/trail/us/utah/kayenta-trail"

class Review(BaseModel):
    author: str
    date: str
    rating: int
    text: str
    image_urls: List[str]

class ReviewList(BaseModel):
    reviews: List[Review]

def main():
    if not FIRECRAWL_API_KEY or not GEMINI_API_KEY:
        print("❌ Missing API Keys")
        return

    print(f"🕷️  Scraping {TARGET_URL}...")
    app = Firecrawl(api_key=FIRECRAWL_API_KEY)
    
    # 1. Scrape
    try:
        data = app.scrape(url=TARGET_URL, formats=['markdown'])
        markdown = data.markdown if hasattr(data, 'markdown') else data.get('markdown', '')
        
        print(f"✅ Scraped {len(markdown)} characters.")
        
        # Save raw for inspection
        with open("debug_kayenta_raw.md", "w") as f:
            f.write(markdown)
            
    except Exception as e:
        print(f"❌ Scrape failed: {e}")
        return

    # 2. Extract with Gemini
    print("🧠 Extracting Top 5 Reviews...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Analyze this hiking trail page content.
    Extract the TOP 5 most recent or relevant reviews.
    
    For each review, capture:
    - Author Name
    - Date (YYYY-MM-DD or relative string like '2 days ago')
    - Rating (1-5 star)
    - Review Text (Full text)
    - Image URLs (Look for image links associated with the review user or review section)
    
    MARKDOWN CONTENT (First 30k chars):
    {markdown[:30000]}
    """
    
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={'response_mime_type': 'application/json', 'response_schema': ReviewList}
        )
        
        if response.parsed:
            print("\n-------------- EXTRACTED REVIEWS --------------")
            for i, r in enumerate(response.parsed.reviews):
                print(f"\n#{i+1} {r.author} ({r.rating}★) - {r.date}")
                print(f"   \"{r.text[:100]}...\"")
                if r.image_urls:
                    print(f"   📷 Images: {len(r.image_urls)} found")
                    for img in r.image_urls:
                        print(f"      - {img}")
                else:
                    print("   (No images)")
        else:
            print("❌ Parsing failed (No content)")

    except Exception as e:
        print(f"❌ Extraction failed: {e}")

if __name__ == "__main__":
    main()
