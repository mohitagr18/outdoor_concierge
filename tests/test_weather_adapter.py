import sys
import os
import json
import pytest

# Ensure app module is visible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.adapters.weather_adapter import parse_weather_data, estimate_temp_at_elevation

# --- MOCK DATA (Recreated from your weather.json attachment) ---
MOCK_WEATHER_JSON = {
  "location": {
    "name": "Lake Mary",
    "region": "California"
  },
  "current": {
    "temp_f": 54.0,
    "condition": {
      "text": "Partly Cloudy",
      "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png",
      "code": 1003
    }
  },
  "forecast": {
    "forecastday": [
      {
        "date": "2025-12-21",
        "day": {
          "maxtemp_f": 39.9,
          "mintemp_f": 31.6,
          "avgtemp_f": 36.1,
          "daily_chance_of_rain": 86,
          "condition": {"text": "Moderate rain"},
          "uv": 0.5
        },
        "astro": {
          "sunrise": "07:08 AM",
          "sunset": "04:41 PM"
        }
      },
      {
        "date": "2025-12-22",
        "day": {
          "maxtemp_f": 42.6,
          "mintemp_f": 29.1,
          "avgtemp_f": 34.3,
          "daily_chance_of_rain": 0,
          "condition": {"text": "Partly Cloudy"},
          "uv": 0.5
        }
      }
    ]
  },
  "alerts": {
    "alert": [
      {
        "headline": "High Wind Warning issued...",
        "severity": "Severe",
        "event": "High Wind Warning",
        "effective": "2025-12-20T13:39:00-08:00",
        "expires": "2025-12-22T04:00:00-08:00"
      }
    ]
  }
}

def test_parse_weather_data():
    """Verify parsing of full weather JSON."""
    summary = parse_weather_data(MOCK_WEATHER_JSON, park_code="yose")

    # Check Top Level
    assert summary.parkCode == "yose"
    assert summary.current_temp_f == 54.0
    assert summary.current_condition == "Partly Cloudy"

    # Check Forecast
    assert len(summary.forecast) == 2
    assert summary.forecast[0].date == "2025-12-21"
    assert summary.forecast[0].maxtemp_f == 39.9
    assert summary.forecast[0].condition == "Moderate rain"

    # Check Astro (Extracted from first day)
    assert summary.sunrise == "07:08 AM"
    assert summary.sunset == "04:41 PM"

    # Check Alerts
    assert len(summary.weather_alerts) == 1
    assert summary.weather_alerts[0]["event"] == "High Wind Warning"
    assert summary.weather_alerts[0]["severity"] == "Severe"


def test_estimate_temp_at_higher_elevation():
    """Test lapse rate for going up in elevation (colder)."""
    # Base: 50°F at 8000 ft
    # Target: 9100 ft (1100 ft higher) -> expect ~3.85°F cooler
    result = estimate_temp_at_elevation(50.0, 8000, 9100)
    assert 46.0 <= result <= 46.2  # ~46.15°F


def test_estimate_temp_at_lower_elevation():
    """Test lapse rate for going down in elevation (warmer)."""
    # Base: 50°F at 8000 ft
    # Target: 7000 ft (1000 ft lower) -> expect 3.5°F warmer
    result = estimate_temp_at_elevation(50.0, 8000, 7000)
    assert 53.4 <= result <= 53.6  # ~53.5°F


def test_estimate_temp_same_elevation():
    """Test lapse rate returns same temp at same elevation."""
    result = estimate_temp_at_elevation(50.0, 8000, 8000)
    assert result == 50.0


if __name__ == "__main__":
    try:
        test_parse_weather_data()
        test_estimate_temp_at_higher_elevation()
        test_estimate_temp_at_lower_elevation()
        test_estimate_temp_same_elevation()
        print("✅ ALL WEATHER ADAPTER TESTS PASSED")
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        raise
