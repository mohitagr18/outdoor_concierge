import json
import os
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import Firecrawl

load_dotenv()

API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not API_KEY:
    print("Error: FIRECRAWL_API_KEY not found in .env")
    exit(1)

def datetime_handler(obj):
    """JSON serializer for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def extract_alltrails_data():
    """
    Use Firecrawl's extract() method to get structured data.
    """
    target_url = "https://www.alltrails.com/trail/us/utah/angels-landing-trail"
    print(f"Extracting structured data from {target_url}...")

    firecrawl = Firecrawl(api_key=API_KEY)

    extract_schema = {
        "type": "object",
        "properties": {
            "trail_metadata": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "park_name": {"type": "string"},
                    "rating": {"type": "number"},
                    "total_reviews": {"type": "integer"},
                    "difficulty": {"type": "string"},
                    "length_miles": {"type": "number"},
                    "elevation_gain_feet": {"type": "integer"},
                    "route_type": {"type": "string"},
                    "description": {"type": "string"},
                    "features": {
                        "type": "object",
                        "properties": {
                            "fee_required": {"type": "boolean"},
                            "dogs_allowed": {"type": "boolean"},
                            "partially_paved": {"type": "boolean"},
                            "scramble": {"type": "boolean"},
                            "bathrooms_available": {"type": "boolean"}
                        }
                    },
                    "top_sights": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"}
                            }
                        }
                    },
                    "trailgoers_summary": {"type": "string"}
                }
            },
            "recent_reviews": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "author": {"type": "string"},
                        "date": {"type": "string"},
                        "rating": {"type": "number"},
                        "review_text": {"type": "string"},
                        "condition_tags": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "image_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 2
                        }
                    }
                },
                "minItems": 5,
                "maxItems": 10
            }
        }
    }

    try:
        print("⏳ Extracting (this may take 30-60 seconds)...")
        
        result = firecrawl.extract(
            urls=[target_url],
            schema=extract_schema,
            prompt="Extract trail information including metadata and the 5-10 most recent reviews with their condition tags and image URLs"
        )
        
        # Use Pydantic's model_dump with mode='json' to handle datetime serialization
        if hasattr(result, 'model_dump'):
            result_dict = result.model_dump(mode='json')
        elif hasattr(result, 'dict'):
            result_dict = result.dict()
        else:
            result_dict = result
        
        # Save with datetime handler
        os.makedirs("data_samples/firecrawl", exist_ok=True)
        with open("data_samples/firecrawl/alltrails_angels_landing_extract.json", "w") as f:
            json.dump(result_dict, f, indent=2, default=datetime_handler)
        
        print("✅ Success: Saved to data_samples/firecrawl/alltrails_angels_landing_extract.json")
        
        # Print summary
        print(f"\n📊 Result type: {type(result_dict)}")
        print(f"   Keys: {list(result_dict.keys()) if isinstance(result_dict, dict) else 'Not a dict'}")
        
        if isinstance(result_dict, dict) and 'data' in result_dict:
            data = result_dict['data']
            print(f"\n   Extracted data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            if 'trail_metadata' in data:
                print(f"   Trail: {data['trail_metadata'].get('name', 'N/A')}")
            
            if 'recent_reviews' in data:
                print(f"   Reviews: {len(data['recent_reviews'])}")
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    extract_alltrails_data()
