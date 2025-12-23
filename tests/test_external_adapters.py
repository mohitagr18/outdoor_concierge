import sys
import os
import json
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.adapters.alltrails_adapter import parse_trail_data
from app.adapters.external_adapter import parse_amenity_place

# --- MOCK TRAIL DATA (From your scraped_extract_llm.json) ---
MOCK_TRAIL_JSON = {
  "name": "Angels Landing",
  "difficulty": "hard",
  "length_miles": 5.4,
  "elevation_gain_ft": 1488,
  "route_type": "Out and Back",
  "average_rating": 4.9,
  "total_reviews": 1000,
  "description": "Steep hike",
  "features": ["Views"],
  "surface_types": ["Paved", "Rock"],
  "recent_reviews": [
    {
      "author": "Hiker 1", 
      "rating": 5, 
      "date": "2025-12-21", 
      "text": "Great!",
      "condition_tags": ["Icy"],
      "visible_image_urls": ["http://img.com/1.jpg"]
    }
  ]
}

# --- MOCK SERPER DATA ---
MOCK_SERPER_PLACE = {
    "title": "Zion Canyon Medical Clinic",
    "address": "123 Main St, Springdale, UT",
    "rating": 4.5,
    "cid": "123456789",
    "open_now": True
}

def test_parse_trail_data():
    trail = parse_trail_data(MOCK_TRAIL_JSON, park_code="zion")
    
    assert trail.name == "Angels Landing"
    assert trail.parkCode == "zion"
    assert trail.recent_reviews[0].condition_tags == ["Icy"]
    assert trail.surface_types == ["Paved", "Rock"]

def test_parse_amenity():
    amenity = parse_amenity_place(MOCK_SERPER_PLACE, amenity_type="Medical")
    
    assert amenity.name == "Zion Canyon Medical Clinic"
    assert amenity.type == "Medical"
    assert "cid=123456789" in amenity.google_maps_url

if __name__ == "__main__":
    try:
        test_parse_trail_data()
        test_parse_amenity()
        print("✅ EXTERNAL ADAPTERS TESTS PASSED")
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        raise
