import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

def test_gen():
    client = genai.Client(api_key=api_key)
    model = "gemini-3-flash-preview"
    
    print(f"Testing generation with {model}...")
    try:
        response = client.models.generate_content(
            model=model, # Try short name
            contents="Say hello"
        )
        print(f"Success! Response: {response.text}")
    except Exception as e:
        print(f"Error with short name: {e}")
        
        # Try full name
        print("\nRetrying with 'models/' prefix...")
        try:
            response = client.models.generate_content(
                model=f"models/{model}",
                contents="Say hello"
            )
            print(f"Success with prefix! Response: {response.text}")
        except Exception as e2:
            print(f"Error with prefix: {e2}")

if __name__ == "__main__":
    test_gen()
