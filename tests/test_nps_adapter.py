import sys
import os
import json
import pytest

# Ensure app module is visible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.adapters.nps_adapter import parse_nps_park, parse_nps_alerts, parse_nps_events

# --- MOCK DATA (Based on your attachments) ---
MOCK_PARK_DATA = {
    "parkCode": "wrst",
    "fullName": "Wrangell-St. Elias National Park & Preserve",
    "description": "A vast park...",
    "latitude": "61.710445", # String in raw JSON
    "longitude": "-142.985664", # String in raw JSON
    "url": "https://www.nps.gov/wrst",
    "images": [
        {
            "url": "https://www.nps.gov/common/uploads/structured_data/3C7AAD63.jpg",
            "title": "Icy Bay",
            "altText": "Glaciers",
            "caption": "Wrangell-St. Elias",
            "credit": "NPS Photo"
        }
    ],
    "contacts": {
        "phoneNumbers": [{"phoneNumber": "9078225234", "type": "Voice"}],
        "emailAddresses": [{"emailAddress": "wrst_info@nps.gov"}]
    }
}

MOCK_ALERTS_RESPONSE = {
    "total": "2",
    "data": [
        {
            "id": "FFE42F8E-C3CC-4C0C",
            "parkCode": "yose",
            "title": "Vernal and Nevada Falls trail closures",
            "description": "Blasting for trail repair...",
            "category": "Park Closure",
            "url": "https://www.nps.gov/yose/planyourvisit/vernalnevadatrail.htm",
            "lastIndexedDate": "2025-12-16 00:00:00.0"
        }
    ]
}

MOCK_EVENTS_RESPONSE = {
    "data": [
        {
            "title": "Ranger Talk",
            "description": "<p>Join us for a talk.</p>",
            "dateStart": "2025-06-01",
            "isFree": True,
            "times": [{"time": "10:00 AM"}]
        }
    ]
}

def test_parse_nps_park():
    """Verify parsing of a single park object."""
    park = parse_nps_park(MOCK_PARK_DATA)
    
    assert park.parkCode == "wrst"
    assert park.location.lat == 61.710445 # Verified float conversion
    assert park.images[0].title == "Icy Bay"
    assert park.contacts.phoneNumbers[0]["phoneNumber"] == "9078225234"

def test_parse_nps_alerts():
    """Verify parsing of alerts response."""
    alerts = parse_nps_alerts(MOCK_ALERTS_RESPONSE)
    
    assert len(alerts) == 1
    assert alerts[0].title == "Vernal and Nevada Falls trail closures"
    assert alerts[0].category == "Park Closure"

def test_parse_nps_events():
    """Verify parsing of events response."""
    events = parse_nps_events(MOCK_EVENTS_RESPONSE)
    
    assert len(events) == 1
    assert events[0].is_free is True
    assert events[0].times[0]["time"] == "10:00 AM"

if __name__ == "__main__":
    try:
        test_parse_nps_park()
        test_parse_nps_alerts()
        test_parse_nps_events()
        print("✅ NPS ADAPTER TESTS PASSED")
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        raise
