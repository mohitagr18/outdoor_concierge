import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import Firecrawl
from pydantic import BaseModel, Field
from typing import List, Optional
from openai import OpenAI

# Load environment variables
load_dotenv()

# --- Configuration ---
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
OUTPUT_DIR = "data_samples/firecrawl"
TARGET_URL = "https://www.alltrails.com/trail/us/utah/angels-landing-trail"

if not FIRECRAWL_API_KEY:
    raise ValueError("FIRECRAWL_API_KEY not found. Check .env")
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not found.")

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
# ... imports ...

def extract_with_local_llm(markdown_content: str):
    print(f"\n--- 2. Extracting (Local LLM - Aggressive Mode) ---")
    if not OPENAI_API_KEY: return None

    client = OpenAI(api_key=OPENAI_API_KEY)
    today_str = datetime.now().strftime("%B %d, %Y")
    
    # AGGRESSIVE PROMPT
    system_prompt = (
    f"Today is {today_str}. You are a precise data extraction engine. "
    "Your goal is to extract trail data from the provided markdown. "
    
    "CRITICAL RULES FOR REVIEWS:\n"
    "1. EXTRACT ALL REVIEWS found in the text, up to 10 reviews maximum.\n"
    "2. DO NOT SKIP reviews that lack images. Text-only reviews are VALID and MUST be included.\n"
    "3. Process reviews sequentially - do NOT stop after finding only reviews with images.\n"
    "4. FOR IMAGE EXTRACTION: After extracting each review's text content, check if image links follow it.\n"
    "   - Image links appear as: `[![alt](url)](link)` or `![alt](url)`\n"
    "   - If images exist: capture ALL valid image URLs for that review\n"
    "   - If NO images exist: set `visible_image_urls` to an empty array []\n"
    "5. CONTINUE extracting the next review regardless of whether the previous one had images.\n"
    "6. DATES: Convert relative dates ('Yesterday', '2 days ago', etc.) to actual dates based on today: {today_str}\n"
    "7. ORDER: Preserve the exact order found in the markdown (typically newest first).\n"
    "8. COMPLETENESS: Extract reviews until you reach 10 OR run out of reviews in the text, whichever comes first.\n"
    
    "\nEXAMPLE LOGIC:\n"
    "- Review 1: Has text + image → Extract both\n"
    "- Review 2: Has text only → Extract text, set visible_image_urls: []\n"
    "- Review 3: Has text + 2 images → Extract text and both images\n"
    "- Continue for ALL reviews found...\n"
    )


    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                # Pass 50k chars to be safe we don't cut off the review list
                {"role": "user", "content": markdown_content[:50000]} 
            ],
            response_format=TrailData,
        )
        return completion.choices[0].message.parsed
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
        if OPENAI_API_KEY:
            data = extract_with_local_llm(md)
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
