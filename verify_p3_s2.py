import os
import sys
import logging
from dotenv import load_dotenv

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.logging_config import setup_logging
from app.services.llm_service import GeminiLLMService
from app.clients.nps_client import NPSClient
from app.clients.weather_client import WeatherClient
from app.orchestrator import OutdoorConciergeOrchestrator, OrchestratorRequest

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Phase 3 - Step 2 Orchestrator Verification...")

    # 1. Setup API Keys
    nps_key = os.getenv("NPS_API_KEY")
    weather_key = os.getenv("WEATHER_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not all([nps_key, weather_key, gemini_key]):
        logger.error("Missing one or more API keys in .env")
        return

    # 2. Initialize Components
    logger.info("Initializing Services...")
    llm_service = GeminiLLMService(api_key=gemini_key)
    nps_client = NPSClient(api_key=nps_key)
    weather_client = WeatherClient(api_key=weather_key)

    orchestrator = OutdoorConciergeOrchestrator(
        llm_service=llm_service,
        nps_client=nps_client,
        weather_client=weather_client
    )

    # 3. Interactive Loop
    print("\n🌲 Orchestrator Ready. (Type 'quit' to exit)")
    print("Try: 'I want an easy dog friendly hike in Zion'")
    
    while True:
        try:
            user_input = input("\nUser: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        req = OrchestratorRequest(user_query=user_input)
        
        try:
            # RUN THE PIPELINE
            resp = orchestrator.handle_query(req)
            
            # Print Structured Debug Info
            print("\n--- 🧠 DEBUG CONTEXT ---")
            print(f"Park: {resp.parsed_intent.park_code}")
            print(f"Intent: {resp.parsed_intent.user_prefs}")
            if resp.park_context:
                print(f"Park Fetched: {resp.park_context.fullName}")
            print(f"Trails Found (Pre-filter): 3 (Mocked)")
            print(f"Trails Vetted: {len(resp.vetted_trails)}")
            print(f"Safety Status: {resp.chat_response.safety_status}")
            
            # Print Final Chat Output
            print("\n--- 🤖 AGENT RESPONSE ---")
            print(resp.chat_response.message)
            print("-" * 40)

        except Exception as e:
            logger.exception("Orchestration failed")
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
