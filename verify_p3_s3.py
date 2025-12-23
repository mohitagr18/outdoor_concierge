import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.logging_config import setup_logging
from app.services.llm_service import GeminiLLMService
from app.clients.nps_client import NPSClient
from app.clients.weather_client import WeatherClient
from app.clients.external_client import ExternalClient
from app.orchestrator import OutdoorConciergeOrchestrator, OrchestratorRequest, SessionContext

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Phase 3 - Step 3 Context Verification...")
    
    # 1. Init
    llm = GeminiLLMService(api_key=os.getenv("GEMINI_API_KEY"))
    orch = OutdoorConciergeOrchestrator(
        llm_service=llm,
        nps_client=NPSClient(api_key=os.getenv("NPS_API_KEY")),
        weather_client=WeatherClient(api_key=os.getenv("WEATHER_API_KEY")),
        external_client=ExternalClient() # New
    )

    # 2. Simulate Client State
    # This represents st.session_state
    client_context = SessionContext() 

    print("\n🌲 Multi-Turn Chat Ready. (Type 'quit' to exit)")
    print("Session is active. Try context follow-ups:")
    print("  1. 'Plan a trip to Zion'")
    print("  2. 'Actually, make it 3 days' (Should verify Zion context)")
    
    while True:
        try:
            user_input = input("\nUser: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        # Pass current state
        req = OrchestratorRequest(
            user_query=user_input,
            session_context=client_context
        )
        
        try:
            resp = orch.handle_query(req)
            
            # Update Client State with the new state from backend
            client_context = resp.updated_context
            
            # Debug Output
            print("\n--- 🧠 CONTEXT DEBUG ---")
            print(f"Current Park: {client_context.current_park_code}")
            print(f"History Length: {len(client_context.chat_history)}")
            
            # Agent Output
            print("\n--- 🤖 AGENT RESPONSE ---")
            print(resp.chat_response.message)
            print("-" * 40)

        except Exception as e:
            logger.exception("Orchestration failed")
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
