
import os
import sys
import logging
from dotenv import load_dotenv
load_dotenv(override=True) # Ensure we have the env vars

from app.services.llm_service import GeminiLLMService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_key = os.getenv("GEMINI_API_KEY")

try:
    print("\n--- Instantiating Service WITHOUT explicit model_name ---")
    # This mimics main.py
    service = GeminiLLMService(api_key=api_key) 
    
    print(f"Service Model Name: {service.model_name}")
    print(f"Agent Coordinator Model: {service.agent_coordinator.model_name}")
    
    if service.agent_coordinator.model_name is None:
        print("CRITICAL: Agent Coordinator model name is None!")
    elif service.agent_coordinator.model_name == "{model}":
        print("CRITICAL: Agent Coordinator model name is literal '{model}'!")
    else:
        print("Agent Coordinator model name seems ok.")

    # Try execution
    query = "Reviews for Kayenta trail?"
    print(f"\n--- Testing Intent Parsing: '{query}' ---")
    intent = service.parse_user_intent(query)
    print("Intent parsed successfully.")

except Exception as e:
    print(f"Test FAILED: {e}")
