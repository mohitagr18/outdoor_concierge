import os
import json
import requests
import urllib.parse
from dotenv import load_dotenv

load_dotenv()
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

def get_places(query, limit=3):
    url = "https://google.serper.dev/places"
    payload = json.dumps({"q": query, "gl": "us", "hl": "en"})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        return response.json().get("places", [])[:limit]
    except Exception as e:
        print(f"Error: {e}")
        return []

def main():
    if not SERPER_API_KEY: return

    city = "Springdale, UT"
    categories = ["Urgent Care", "Grocery Store"] # Just 2 for debug

    print(f"--- Debugging Serper Output for {city} ---\n")

    for cat in categories:
        query = f"{cat} near {city}"
        results = get_places(query, limit=1) # Limit 1 to keep log clean
        
        if results:
            item = results[0]
            
            # --- 1. INSPECT RAW JSON FOR HOURS ---
            # print(f"DEBUG RAW: {json.dumps(item, indent=2)}") 
            
            # --- 2. Extract Fields ---
            name = item.get("title")
            addr = item.get("address")
            rating = item.get("rating", "N/A")
            
            # Construct Google Maps Link
            # Best way: Use the 'cid' if available, else query
            cid = item.get("cid")
            if cid:
                map_url = f"https://maps.google.com/?cid={cid}"
            else:
                encoded_query = urllib.parse.quote(f"{name} {addr}")
                map_url = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"

            print(f"Name: {name} ({rating}★)")
            print(f"Link: {map_url}")
            print(f"Status Data Found? 'open_now'={item.get('open_now')}, 'hours'={item.get('hours')}")
            print("-" * 30)

if __name__ == "__main__":
    main()
