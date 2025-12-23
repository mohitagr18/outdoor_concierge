from typing import List, Dict, Any, Optional
from app.models import ParkContext, Alert, Event, GeoLocation, ParkContact, ParkImage

def parse_nps_park(park_data: Dict[str, Any]) -> ParkContext:
    """
    Parses a SINGLE park object from the NPS 'parks' endpoint data list.
    Note: Input is one dictionary from the 'data' list, not the whole response.
    """
    # 1. Extract Lat/Lon safely
    try:
        lat = float(park_data.get("latitude", 0.0) or 0.0)
        lon = float(park_data.get("longitude", 0.0) or 0.0)
    except ValueError:
        lat, lon = 0.0, 0.0

    # 2. Extract Contacts
    raw_contacts = park_data.get("contacts", {})
    contacts = ParkContact(
        phoneNumbers=raw_contacts.get("phoneNumbers", []),
        emailAddresses=raw_contacts.get("emailAddresses", [])
    )

    # 3. Extract Images
    raw_images = park_data.get("images", [])
    images = []
    for img in raw_images:
        images.append(ParkImage(
            url=img.get("url", ""),
            title=img.get("title"),
            altText=img.get("altText"),
            caption=img.get("caption"),
            credit=img.get("credit")
        ))

    return ParkContext(
        parkCode=park_data.get("parkCode", ""),
        fullName=park_data.get("fullName", "Unknown Park"),
        description=park_data.get("description", ""),
        location=GeoLocation(lat=lat, lon=lon),
        contacts=contacts,
        operatingHours=park_data.get("operatingHours", []),
        url=park_data.get("url", ""),
        images=images
    )

def parse_nps_alerts(alerts_response: Dict[str, Any]) -> List[Alert]:
    """
    Parses the full JSON response from the 'alerts' endpoint.
    """
    data_list = alerts_response.get("data", [])
    alerts = []
    
    for item in data_list:
        alerts.append(Alert(
            id=item.get("id", ""),
            parkCode=item.get("parkCode", ""),
            title=item.get("title", "No Title"),
            description=item.get("description", ""),
            category=item.get("category", "Information"),
            url=item.get("url"),
            lastIndexedDate=item.get("lastIndexedDate", "")
        ))
    
    return alerts

def parse_nps_events(events_response: Dict[str, Any]) -> List[Event]:
    """
    Parses the full JSON response from the 'events' endpoint.
    """
    data_list = events_response.get("data", [])
    events = []

    for item in data_list:
        # Flatten times if they exist
        times = item.get("times", [])
        
        events.append(Event(
            title=item.get("title", "No Title"),
            description=item.get("description", ""), # Removing HTML in future steps if needed
            date_start=item.get("dateStart", ""),
            date_end=item.get("dateEnd"),
            is_free=item.get("isFree", False),
            location=item.get("location", ""),
            times=times
        ))
    
    return events
