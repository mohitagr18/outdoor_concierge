import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

def list_models():
    print(f"Key present: {bool(api_key)}")
    client = genai.Client(api_key=api_key)
    
    print("Introspecting client.models...")
    print(dir(client.models))
    
    try:
        # Try finding a list method
        if hasattr(client.models, 'list'):
            print("\nCalling client.models.list()...")
            for m in client.models.list():
                print(f" - {m.name}")
        elif hasattr(client.models, 'list_models'):
            print("\nCalling client.models.list_models()...")
            for m in client.models.list_models():
                print(f" - {m.name}")
        else:
            print("\nCould not find list method. Trying generic v1beta list.")
            # Fallback to direct http check if SDK is confusing
            
    except Exception as e:
        print(f"Error inspecting models: {e}")

if __name__ == "__main__":
    list_models()
