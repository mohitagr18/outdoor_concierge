import os
import sys
import logging

from dotenv import load_dotenv

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.engine.constraints import UserPreference, SafetyStatus
from app.models import TrailSummary
from app.services.llm_service import GeminiLLMService
from app.logging_config import setup_logging

load_dotenv()

setup_logging()
logger = logging.getLogger(__name__)
    

def main() -> None:
    logger.info("Starting LLM Service Step 1 Verification...")

    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-3-flash-preview")

    if not api_key:
        logger.error("Missing GEMINI_API_KEY in .env")
        return

    llm = GeminiLLMService(api_key=api_key, model_name=model_name)

    # Simple REPL-style loop
    while True:
        try:
            query = input("\nEnter a user query (or 'quit'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not query or query.lower() in {"q", "quit", "exit"}:
            print("Goodbye.")
            break

        try:
            intent = llm.parse_user_intent(query)
        except Exception as e:
            logger.exception("Error parsing user intent: %s", e)
            continue

        print("\n--- Parsed Intent ---")
        print(intent.model_dump_json(indent=2))

        # For Step 1, we just pass a dummy safety + trails to generate_response
        dummy_safety = SafetyStatus(status="Go", reason=[])
        dummy_trails = [
            TrailSummary(
                name="Sample Trail",
                parkCode=intent.park_code or "yose",
                difficulty=intent.user_prefs.max_difficulty,
                length_miles=min(intent.user_prefs.max_length_miles, 5.0),
                elevation_gain_ft=500,
                route_type="out and back",
                average_rating=4.5,
                total_reviews=100,
                description="Sample trail for LLM testing.",
                features=["dogs on leash"] if intent.user_prefs.dog_friendly else [],
                surface_types=["dirt"],
            )
        ]

        resp = llm.generate_response(
            query=query,
            intent=intent,
            safety=dummy_safety,
            trails=dummy_trails,
        )

        print("\n--- Generated Response ---")
        print(resp.message)


if __name__ == "__main__":
    main()
