#!/usr/bin/env python3
"""
Debug script to validate WeatherAPI responses for zonal weather.
This shows the raw API data to help identify discrepancies.
"""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("WEATHER_API_KEY")
if not API_KEY:
    print("ERROR: WEATHER_API_KEY not set in .env")
    exit(1)

# Yosemite zones from park_details.json
ZONES = [
    {"name": "Yosemite Valley", "lat": 37.7456, "lon": -119.5936, "configured_elev": 4000},
    {"name": "Glacier Point", "lat": 37.7308, "lon": -119.5728, "configured_elev": 7200},
    {"name": "Tioga Pass", "lat": 37.9106, "lon": -119.2569, "configured_elev": 9943},
]

print("=" * 70)
print("WEATHERAPI DEBUG: Raw API Response vs Zone Configuration")
print("=" * 70)

for zone in ZONES:
    url = f"http://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": API_KEY,
        "q": f"{zone['lat']},{zone['lon']}",
        "days": 1,
        "aqi": "no",
        "alerts": "no"
    }
    
    print(f"\n--- {zone['name']} ---")
    print(f"Request: q={zone['lat']},{zone['lon']}")
    print(f"Configured elevation: {zone['configured_elev']} ft")
    
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        
        # Location info (includes API's internal elevation if available)
        loc = data.get("location", {})
        print(f"\nAPI Response Location:")
        print(f"  Name: {loc.get('name')}, {loc.get('region')}")
        print(f"  Coords: {loc.get('lat')}, {loc.get('lon')}")
        
        # Current weather
        current = data.get("current", {})
        print(f"\nCurrent Weather (from API):")
        print(f"  Temp: {current.get('temp_f')}°F")
        print(f"  Condition: {current.get('condition', {}).get('text')}")
        print(f"  Last Updated: {current.get('last_updated')}")
        
        # Today's forecast
        forecast = data.get("forecast", {}).get("forecastday", [])
        if forecast:
            day = forecast[0].get("day", {})
            print(f"\nToday's Forecast:")
            print(f"  High: {day.get('maxtemp_f')}°F")
            print(f"  Low: {day.get('mintemp_f')}°F")
            print(f"  Avg: {day.get('avgtemp_f')}°F")
            
            # Validate: current should be between low and high (roughly)
            curr_temp = current.get('temp_f', 0)
            low = day.get('mintemp_f', 0)
            high = day.get('maxtemp_f', 100)
            
            if curr_temp < low - 5 or curr_temp > high + 5:
                print(f"\n  ⚠️  WARNING: Current temp ({curr_temp}°F) is outside forecast range ({low}-{high}°F)!")
            else:
                print(f"\n  ✅ Current temp is within expected range")
                
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "=" * 70)
print("To validate manually, visit:")
print("https://www.weatherapi.com/api-explorer.aspx")
print("And compare with actual weather at:")
print("https://www.nps.gov/yose/planyourvisit/conditions.htm")
print("=" * 70)
