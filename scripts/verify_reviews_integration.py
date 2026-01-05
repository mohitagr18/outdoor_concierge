import os
import json
import logging
from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Env
load_dotenv()

# Imports - Adjust path if needed
from app.services.llm_service import GeminiLLMService
from app.services.review_scraper import ReviewScraper
from app.services.data_manager import DataManager
from app.orchestrator import OutdoorConciergeOrchestrator, OrchestratorRequest, SessionContext
from app.clients.nps_client import NPSClient
from app.clients.weather_client import WeatherClient
from app.clients.external_client import ExternalClient

# Mocks
class MockClient:
    def __getattr__(self, name):
        return lambda *args, **kwargs: []

def verify():
    # 1. Config
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Missing GEMINI_API_KEY")
        return

    park_code = "zion"
    trail_name = "Kayenta Trail"
    
    # 2. Reset Cache (Optional: Clear 'recent_reviews' from trails_v2.json for this trail to force scrape? 
    # Or just let it check cache validity. Let's assume clear to verify scrape.)
    
    # 3. Init Services
    # Force a known working model to avoid 404s
    llm = GeminiLLMService(api_key=api_key, model_name="gemini-3-flash-preview")
    # Using real scraper
    scraper = ReviewScraper(llm)
    
    # Init Orchestrator with Mocks and Real LLM
    orch = OutdoorConciergeOrchestrator(
        llm_service=llm,
        nps_client=MockClient(),
        weather_client=MockClient(),
        external_client=MockClient()
    )
    # Inject real scraper (orchestrator inits its own, but let's confirm it's working inside)
    
    # 4. Simulate Query
    query = f"What are the latest reviews for {trail_name}?"
    print(f"\n🧪 Testing Query: '{query}'")
    
    req = OrchestratorRequest(
        user_query=query,
        session_context=SessionContext(current_park_code=park_code)
    )
    
    # 5. Run Orchestrator
    resp = orch.handle_query(req)
    
    # 6. Analyze Result
    print("\n🔍 Analysis:")
    print(f"Parsed Intent Type: {resp.parsed_intent.response_type} (Expected: 'reviews')")
    print(f"Review Targets: {resp.parsed_intent.review_targets}")
    
    print("\n💬 Agent Response:")
    print(resp.chat_response.message)
    
    # Validate Cache
    dm = DataManager()
    trails = dm.load_fixture(park_code, "trails_v2.json")
    target = next((t for t in trails if trail_name.lower() in t["name"].lower()), None)
    
    if target and target.get("recent_reviews"):
        print(f"\n✅ Cache Updated? YES. Found {len(target['recent_reviews'])} reviews in trails_v2.json")
        print(f"   Last Updated: {target.get('reviews_last_updated')}")
    else:
        print("\n❌ Cache Updated? NO. recent_reviews missing or empty.")

if __name__ == "__main__":
    verify()
