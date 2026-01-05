import os
import json
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any

try:
    from firecrawl import FirecrawlApp as Firecrawl # Updated class name if needed, or check docs. Actually let's assume FirecrawlApp is the standard now or check imports.
    # Wait, simple 'from firecrawl import Firecrawl' might be wrong for v1.0+.
    # Let's just log the error to see.
    from firecrawl import FirecrawlApp as Firecrawl
except ImportError as e:
    logging.error(f"Failed to import firecrawl: {e}")
    Firecrawl = None

from app.services.llm_service import GeminiLLMService
from app.services.data_manager import DataManager
from app.models import TrailReview

logger = logging.getLogger(__name__)

class ReviewScraper:
    def __init__(self, llm_service: GeminiLLMService):
        self.llm = llm_service
        self.data_manager = DataManager()
        self.api_key = os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            logger.warning("FIRECRAWL_API_KEY not found. Scraping will be disabled.")

    def fetch_reviews(self, park_code: str, trail_name: str) -> List[TrailReview]:
        """
        Fetches reviews for a specific trail.
        1. Checks local trails_v2.json for cached reviews from TODAY.
        2. If stale/missing, scrapes AllTrails using Firecrawl.
        3. Extracts reviews using LLM.
        4. Updates trails_v2.json cache.
        """
        # 1. Load local cache
        # We use the DataManager to get the path, but we need to write back too.
        trails_data = self.data_manager.load_fixture(park_code, "trails_v2.json")
        if not trails_data:
            logger.warning(f"No trails_v2.json found for {park_code}")
            return []

        # 2. Find target trail (fuzzy match name)
        target_trail = None
        trail_name_lower = trail_name.lower()
        
        # Try exact match first
        for t in trails_data:
            if t.get("name", "").lower() == trail_name_lower:
                target_trail = t
                break
        
        # Try contained match if not found
        if not target_trail:
            for t in trails_data:
                if trail_name_lower in t.get("name", "").lower():
                    target_trail = t
                    break
        
        if not target_trail:
            logger.warning(f"Trail '{trail_name}' not found in local DB.")
            return []

        # 3. Check Cache Validity (Today)
        # We look for a separate timestamp for reviews if we want to be precise, 
        # or just use last_enriched if we update it.
        # Let's check 'reviews_last_updated' first, then fall back to 'last_enriched' logic if needed.
        last_updated = target_trail.get("reviews_last_updated")
        
        if last_updated:
            try:
                dt = datetime.fromisoformat(last_updated).date()
                if dt == date.today() and target_trail.get("recent_reviews"):
                   logger.info(f"Using cached reviews for {trail_name} (Updated: {last_updated})")
                   return [TrailReview(**r) for r in target_trail["recent_reviews"]]
            except ValueError:
                pass

        # 4. Scrape logic
        if not self.api_key:
            logger.warning("Skipping scrape: No API Key")
            # FALLBACK: Return cached reviews if they exist, even if stale
            if target_trail.get("recent_reviews"):
                logger.info("Using cached reviews (Fallback - No API Key)")
                return [TrailReview(**r) for r in target_trail["recent_reviews"]]
            return []
            
        if not Firecrawl:
            logger.warning("Skipping scrape: Firecrawl module not installed")
            # FALLBACK: Return cached reviews if they exist
            if target_trail.get("recent_reviews"):
                logger.info("Using cached reviews (Fallback - No Firecrawl)")
                return [TrailReview(**r) for r in target_trail["recent_reviews"]]
            return []

        url = target_trail.get("alltrails_url")
        
        # Sanity check URL
        if not url or "alltrails" not in url:
             logger.warning(f"No valid AllTrails URL for {trail_name}: {url}")
             return []

        logger.info(f"🕷️ Scraping reviews for '{target_trail['name']}' from {url}")
        try:
             app = Firecrawl(api_key=self.api_key)
             # V2: returns an object, not just dict
             scraped = app.scrape_url(url, params={'formats': ['markdown']})
             
             markdown = ""
             if hasattr(scraped, 'markdown'):
                 markdown = scraped.markdown
             elif isinstance(scraped, dict):
                 markdown = scraped.get('markdown', '')
             
             if not markdown:
                 logger.error("Empty scrape result")
                 # FALLBACK
                 if target_trail.get("recent_reviews"):
                    logger.info("Using cached reviews (Fallback - Empty Scrape)")
                    return [TrailReview(**r) for r in target_trail["recent_reviews"]]
                 return []

             # 5. Extract
             logger.info("🧠 Extracting reviews with Gemini...")
             reviews = self.llm.extract_reviews_from_text(markdown)
             
             if reviews:
                 logger.info(f"✅ Found {len(reviews)} reviews. updating cache.")
                 # 6. Update Cache
                 target_trail["recent_reviews"] = [r.model_dump() for r in reviews]
                 target_trail["reviews_last_updated"] = datetime.now().isoformat()
                 target_trail["last_enriched"] = datetime.now().isoformat()

                 # 7. Recalculate Stats (Rating/Count)
                 if reviews:
                     avg_rating = sum(r.rating for r in reviews) / len(reviews)
                     target_trail["average_rating"] = round(avg_rating, 1)
                     target_trail["total_reviews"] = len(reviews) 
                 
                 # Save back to disk
                 self._save_cache(park_code, trails_data)
                 
                 return reviews
             else:
                 logger.warning("LLM found 0 reviews in the scraped content.")
                 # FALLBACK
                 if target_trail.get("recent_reviews"):
                     return [TrailReview(**r) for r in target_trail["recent_reviews"]]
             
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            # FALLBACK
            if target_trail.get("recent_reviews"):
                logger.info("Using cached reviews (Fallback - Scrape Exception)")
                return [TrailReview(**r) for r in target_trail["recent_reviews"]]
            return []

        return []

    def _save_cache(self, park_code: str, data: List[Dict]):
        # Construct path using DataManager base_dir logic manually 
        # (Assuming standard structure: data_samples/ui_fixtures/{PARK}/trails_v2.json)
        path = os.path.join(self.data_manager.base_dir, park_code.upper(), "trails_v2.json")
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"💾 Saved updated cache to {path}")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
