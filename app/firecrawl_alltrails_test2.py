import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import Firecrawl
from pydantic import BaseModel, Field
from typing import List, Optional
from google import genai

# Load environment variables
load_dotenv()

# --- Configuration ---
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Using Gemini Key
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
OUTPUT_DIR = "data_samples/firecrawl"
TARGET_URL = "https://www.alltrails.com/trail/us/utah/angels-landing-trail"

if not FIRECRAWL_API_KEY:
    raise ValueError("FIRECRAWL_API_KEY not found. Check .env")
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found.")

# --- Models ---
class Review(BaseModel):
    author: str
    rating: int
    date: str
    text: str
    condition_tags: List[str] = []
    visible_image_urls: List[str] = []
    activity_url: Optional[str] = None

class TrailData(BaseModel):
    name: str
    difficulty: str
    length_miles: float
    elevation_gain_ft: int
    route_type: str
    average_rating: float
    total_reviews: int
    description: str
    features: List[str] = []
    surface_types: List[str] = []
    recent_reviews: List[Review] = []

# --- 1. Scrape ---
def scrape_trail_markdown(app: Firecrawl, url: str):
    print(f"\n--- 1. Scraping ---")
    start = time.time()
    try:
        # CORRECTED LINE: formats is a direct keyword argument
        result = app.scrape(url=url, formats=['markdown'])
        print(f"Scrape took {time.time() - start:.2f}s")
        if isinstance(result, dict) and 'markdown' in result:
            return result['markdown']
        return str(result)
    except Exception as e:
        print(f"Scrape error: {e}")
        return None

# --- 2. Extract ---
def extract_with_gemini(markdown_content: str):
    print(f"\n--- 2. Extracting (Gemini - Aggressive Mode) ---")
    if not GEMINI_API_KEY: return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    today_str = datetime.now().strftime("%B %d, %Y")
    
    system_prompt = (
        f"Today is {today_str}. You are a precise data extraction engine. "
        "Your goal is to extract trail data from the provided markdown. "
        
        "CRITICAL RULES FOR REVIEWS:\n"
        "1. EXTRACT ALL REVIEWS found in the text, up to 10 reviews maximum.\n"
        "2. DO NOT SKIP reviews that lack images. Text-only reviews are VALID and MUST be included.\n"
        "3. Process reviews sequentially.\n"
        "4. IMAGE EXTRACTION: Capture valid image URLs if they exist, otherwise [].\n"
        "5. DATES: Convert relative dates ('Yesterday', etc.) to actual dates based on today: {today_str}\n"
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"{system_prompt}\n\nMarkdown Content:\n{markdown_content[:30000]}",
            config={'response_mime_type': 'application/json', 'response_schema': TrailData}
        )
        return response.parsed
    except Exception as e:
        print(f"Extraction error: {e}")
        return None


# --- Main ---
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    try:
        app = Firecrawl(api_key=FIRECRAWL_API_KEY)
    except Exception as e:
        print(f"Init error: {e}")
        return

    md = scrape_trail_markdown(app, TARGET_URL)
    
    if md:
        # Save Raw
        with open(f"{OUTPUT_DIR}/scraped_raw.md", "w", encoding="utf-8") as f:
            f.write(md)
        
        # Extract
        if GEMINI_API_KEY:
            data = extract_with_gemini(md)
            if data:
                # Save JSON
                json_str = data.model_dump_json(indent=2)
                with open(f"{OUTPUT_DIR}/scraped_extract_llm.json", "w", encoding="utf-8") as f:
                    f.write(json_str)
                
                print("\n" + "="*40)
                print(" FINAL JSON OUTPUT ")
                print("="*40)
                print(json_str)
                print("="*40 + "\n")
            else:
                print("Extraction returned None")
    else:
        print("Scrape returned None")

if __name__ == "__main__":
    main()
