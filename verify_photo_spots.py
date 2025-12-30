import sys
import os
import json
from app.models import PhotoSpot

# Add current directory to path so we can import app.models
sys.path.append(os.getcwd())

def verify():
    try:
        with open('data_samples/ui_fixtures/ZION/photo_spots.json', 'r') as f:
            data = json.load(f)
            
        print(f"Loaded {len(data)} items from JSON.")
        
        for i, item in enumerate(data):
            try:
                PhotoSpot(**item)
            except Exception as e:
                print(f"Error validating item {i}: {item.get('name', 'Unknown')}")
                print(e)
                sys.exit(1)
                
        print("Verification Successful: All items match PhotoSpot model.")
        
    except Exception as e:
        print(f"General Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify()
