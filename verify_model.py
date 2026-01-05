
import os
import sys
import logging
from dotenv import load_dotenv
load_dotenv(override=True)

from app.services.llm_service import GeminiLLMService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_key = os.getenv("GEMINI_API_KEY")

try:
    print("\n--- Verifying Gemini-3-Preview Connectivity ---")
    service = GeminiLLMService(api_key=api_key) 
    print(f"Service Model: {service.model_name}")
    print(f"Agent Model: {service.agent_coordinator.model_name}")

    query = "Reviews for Kayenta trail?"
    intent = service.parse_user_intent(query)
    print("Intent parsed successfully.")

except Exception as e:
    print(f"Test FAILED: {e}")
