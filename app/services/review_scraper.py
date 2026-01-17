import os
import json
import logging
import re
import requests
from urllib.parse import quote_plus
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
        from app.utils.fuzzy_match import fuzzy_match_trail_name
        target_trail = None
        trail_name_lower = trail_name.lower()
        
        # Try exact match first
        for t in trails_data:
            if t.get("name", "").lower() == trail_name_lower:
                target_trail = t
                break
        
        # Try fuzzy match if not found
        if not target_trail:
            for t in trails_data:
                if fuzzy_match_trail_name(trail_name, t.get("name", "")):
                    target_trail = t
                    logger.info(f"Fuzzy matched '{trail_name}' to '{t.get('name')}'")
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

        # 4. Check if scraping is even possible before doing URL lookups
        if not self.api_key:
            logger.warning("Skipping scrape: No API Key")
            # FALLBACK: Return cached reviews if they exist, even if stale
            if target_trail.get("recent_reviews"):
                logger.info("Using cached reviews (Fallback - No API Key)")
                return [TrailReview(**r) for r in target_trail["recent_reviews"]]
            # No reviews and can't scrape - return empty and let LLM know
            logger.info(f"No cached reviews for {trail_name} and cannot scrape (no API key)")
            return []
            
        if not Firecrawl:
            logger.warning("Skipping scrape: Firecrawl module not installed")
            if target_trail.get("recent_reviews"):
                logger.info("Using cached reviews (Fallback - No Firecrawl)")
                return [TrailReview(**r) for r in target_trail["recent_reviews"]]
            return []

        # 5. Get or find AllTrails URL
        url = target_trail.get("alltrails_url")
        url_was_discovered = False
        
        # If no AllTrails URL, try to find one dynamically
        if not url or "alltrails" not in url:
            logger.info(f"🔍 No AllTrails URL for '{trail_name}'. Searching...")
            url = self._find_alltrails_url(target_trail['name'], park_code)
            
            if url:
                # Mark URL as newly discovered (will be saved with reviews)
                target_trail["alltrails_url"] = url
                url_was_discovered = True
                logger.info(f"✅ Found AllTrails URL: {url}")
            else:
                logger.warning(f"Could not find AllTrails URL for {trail_name}")
                # FALLBACK: Return cached reviews if they exist
                if target_trail.get("recent_reviews"):
                    logger.info("Using cached reviews (Fallback - No AllTrails URL)")
                    return [TrailReview(**r) for r in target_trail["recent_reviews"]]
                return []

        logger.info(f"🕷️ Scraping reviews for '{target_trail['name']}' from {url}")
        try:
             import concurrent.futures
             
             app = Firecrawl(api_key=self.api_key)
             
             # Use ThreadPoolExecutor for hard timeout (Firecrawl timeout doesn't work reliably)
             def do_scrape():
                 return app.scrape(url, formats=['markdown'], timeout=30000)
             
             with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                 future = executor.submit(do_scrape)
                 try:
                     scraped = future.result(timeout=45)  # 45 second hard timeout
                 except concurrent.futures.TimeoutError:
                     logger.error(f"Firecrawl scrape timed out after 45 seconds for {url}")
                     if target_trail.get("recent_reviews"):
                         return [TrailReview(**r) for r in target_trail["recent_reviews"]]
                     return []
             
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
                 
                 # Save back to disk (includes new URL if discovered)
                 self._save_cache(park_code, trails_data)
                 
                 return reviews
             else:
                 logger.warning("LLM found 0 reviews in the scraped content.")
                 # Still save if we discovered a new URL
                 if url_was_discovered:
                     self._save_cache(park_code, trails_data)
                     logger.info("Saved newly discovered AllTrails URL (no reviews found)")
                 # FALLBACK
                 if target_trail.get("recent_reviews"):
                     return [TrailReview(**r) for r in target_trail["recent_reviews"]]
             
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            # Still save if we discovered a new URL
            if url_was_discovered:
                self._save_cache(park_code, trails_data)
                logger.info("Saved newly discovered AllTrails URL (scrape failed)")
            # FALLBACK
            if target_trail.get("recent_reviews"):
                logger.info("Using cached reviews (Fallback - Scrape Exception)")
                return [TrailReview(**r) for r in target_trail["recent_reviews"]]
            return []

        return []

    def _find_alltrails_url(self, trail_name: str, park_code: str) -> Optional[str]:
        """
        Search for AllTrails URL using DuckDuckGo site-specific search.
        Returns the first AllTrails trail URL found, or None.
        """
        from urllib.parse import unquote
        
        # Map park codes to full names for better search results
        PARK_NAMES = {
            "zion": "Zion National Park",
            "yose": "Yosemite National Park",
            "grca": "Grand Canyon National Park",
            "brca": "Bryce Canyon National Park",
        }
        park_name = PARK_NAMES.get(park_code.lower(), park_code)
        
        # Clean trail name - remove "Trailhead" suffix for better matching
        clean_trail_name = trail_name.replace(" Trailhead", "").replace(" Trail", " Trail")
        
        # Use site-specific search for better results
        search_query = f"site:alltrails.com {clean_trail_name} {park_name}"
        encoded_query = quote_plus(search_query)
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                # Look for URL-encoded AllTrails paths in DuckDuckGo results
                # Pattern matches: alltrails.com%2Ftrail%2F...
                encoded_pattern = r'alltrails\.com%2Ftrail%2F[^&\s"<>]+'
                encoded_matches = re.findall(encoded_pattern, resp.text)
                
                if encoded_matches:
                    # Decode the URL
                    for match in encoded_matches:
                        decoded = unquote(match)
                        clean_url = f"https://www.{decoded}".split('&')[0]
                        if '/trail/' in clean_url:
                            logger.info(f"Found AllTrails URL via search: {clean_url}")
                            return clean_url
                
                # Also try direct URL pattern
                direct_pattern = r'https://www\.alltrails\.com/trail/[^"\s<>]+'
                direct_matches = re.findall(direct_pattern, resp.text)
                
                if direct_matches:
                    for match in direct_matches:
                        clean_url = match.split('?')[0]
                        if '/trail/' in clean_url:
                            logger.info(f"Found AllTrails URL via search: {clean_url}")
                            return clean_url
            
            logger.warning(f"No AllTrails URL found in search results for '{trail_name}'")
            return None
            
        except Exception as e:
            logger.error(f"Search for AllTrails URL failed: {e}")
            return None


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
