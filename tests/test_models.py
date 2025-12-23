import sys
import os
import pytest
from pydantic import ValidationError

# Ensure app module is visible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import (
    ParkContext, 
    WeatherSummary, 
    TrailSummary, 
    Alert,
    GeoLocation,
    ParkImage
)

def test_park_context_full_structure():
    """Test ParkContext with nested images and contacts."""
    park = ParkContext(
        parkCode="yose",
        fullName="Yosemite National Park",
        description="A beautiful valley.",
        location=GeoLocation(lat=37.86, lon=-119.53),
        url="https://nps.gov/yose",
        images=[
            ParkImage(
                url="http://img.com/1.jpg", 
                title="Half Dome",
                altText="Granite dome",
                caption="Iconic"
            )
        ]
    )
    assert park.images[0].title == "Half Dome"
    assert park.location.lat == 37.86

def test_trail_summary_with_surface_types():
    """Test the new surface_types field from scraped data."""
    trail = TrailSummary(
        name="Angels Landing",
        difficulty="hard",
        length_miles=5.4,
        elevation_gain_ft=1488,
        route_type="Out and Back",
        average_rating=4.9,
        total_reviews=1000,
        description="Steep hike.",
        surface_types=["Paved", "Rock"]
    )
    assert "Rock" in trail.surface_types

def test_weather_summary_alerts():
    """Test WeatherSummary with alerts."""
    weather = WeatherSummary(
        parkCode="zion",
        current_temp_f=80.0,
        current_condition="Sunny",
        forecast=[],
        weather_alerts=[{"event": "Flood Watch", "severity": "Severe"}]
    )
    assert weather.weather_alerts[0]['event'] == "Flood Watch"

if __name__ == "__main__":
    try:
        test_park_context_full_structure()
        test_trail_summary_with_surface_types()
        test_weather_summary_alerts()
        print("✅ ALL MODEL TESTS PASSED")
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        raise
