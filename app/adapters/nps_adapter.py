from typing import List, Dict, Any, Optional

from app.models import (
    ParkContext, Alert, Event, GeoLocation, ParkContact, ParkImage,
    Campground, VisitorCenter, Webcam, Place, ThingToDo, PassportStamp, Address
)

# --- HELPER FUNCTIONS ---

def _extract_geo(data: Dict[str, Any]) -> GeoLocation:
    """Safely extracts lat/lon from a dictionary."""
    try:
        lat = float(data.get("latitude", 0.0) or 0.0)
        lon = float(data.get("longitude", 0.0) or 0.0)
        return GeoLocation(lat=lat, lon=lon)
    except ValueError:
        return GeoLocation(lat=0.0, lon=0.0)

def _extract_images(data: Dict[str, Any]) -> List[ParkImage]:
    """Safely extracts a list of images."""
    raw_images = data.get("images", [])
    images = []
    for img in raw_images:
        images.append(ParkImage(
            url=img.get("url", ""),
            title=img.get("title"),
            altText=img.get("altText"),
            caption=img.get("caption"),
            credit=img.get("credit")
        ))
    return images

def _extract_contacts(data: Dict[str, Any]) -> ParkContact:
    """Safely extracts contact info."""
    raw_contacts = data.get("contacts", {})
    return ParkContact(
        phoneNumbers=raw_contacts.get("phoneNumbers", []),
        emailAddresses=raw_contacts.get("emailAddresses", [])
    )

def _extract_addresses(data: Dict[str, Any]) -> List[Address]:
    """Safely extracts address info."""
    raw_addresses = data.get("addresses", [])
    addresses = []
    for addr in raw_addresses:
        addresses.append(Address(
            line1=addr.get("line1"),
            line2=addr.get("line2"),
            line3=addr.get("line3"),
            city=addr.get("city"),
            stateCode=addr.get("stateCode"),
            postalCode=addr.get("postalCode"),
            type=addr.get("type", "Physical")
        ))
    return addresses

# --- MAIN PARSERS ---

def parse_nps_park(park_data: Dict[str, Any]) -> ParkContext:
    """
    Parses a SINGLE park object from the NPS 'parks' endpoint data list.
    """
    return ParkContext(
        parkCode=park_data.get("parkCode", ""),
        fullName=park_data.get("fullName", "Unknown Park"),
        description=park_data.get("description", ""),
        location=_extract_geo(park_data),
        contacts=_extract_contacts(park_data),
        operatingHours=park_data.get("operatingHours", []),
        url=park_data.get("url", ""),
        images=_extract_images(park_data),
        # Child lists are populated by the client, not this parser
        campgrounds=[],
        visitor_centers=[],
        webcams=[],
        places=[],
        things_to_do=[],
        passport_stamps=[]
    )

def parse_nps_alerts(alerts_response: Dict[str, Any]) -> List[Alert]:
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
    data_list = events_response.get("data", [])
    events = []
    for item in data_list:
        events.append(Event(
            title=item.get("title", "No Title"),
            description=item.get("description", ""),
            date_start=item.get("dateStart", ""),
            date_end=item.get("dateEnd"),
            is_free=item.get("isFree", False),
            location=item.get("location", ""),
            times=item.get("times", [])
        ))
    return events

# --- NEW PARSERS FOR EXPANDED SCOPE ---

def parse_nps_campgrounds(response: Dict[str, Any]) -> List[Campground]:
    data_list = response.get("data", [])
    results = []
    for item in data_list:
        # Flatten simple campsite stats
        campsites_raw = item.get("campsites", {})
        campsites = {
            "totalSites": str(campsites_raw.get("totalSites", "0")),
            "tentOnly": str(campsites_raw.get("tentOnly", "0")),
            "rvOnly": str(campsites_raw.get("rvOnly", "0"))
        }

        results.append(Campground(
            id=item.get("id", ""),
            name=item.get("name", "Unknown Campground"),
            description=item.get("description", ""),
            location=_extract_geo(item),
            campsites=campsites,
            accessibility=item.get("accessibility", {}),
            amenities=item.get("amenities", {}),
            contacts=_extract_contacts(item),
            fees=item.get("fees", []),
            images=_extract_images(item),
            reservationUrl=item.get("reservationUrl"),
            isOpen=True # Default to true as API doesn't have a simple bool
        ))
    return results

def parse_nps_visitor_centers(response: Dict[str, Any]) -> List[VisitorCenter]:
    data_list = response.get("data", [])
    results = []
    for item in data_list:
        results.append(VisitorCenter(
            id=item.get("id", ""),
            name=item.get("name", "Unknown Visitor Center"),
            description=item.get("description", ""),
            location=_extract_geo(item),
            url=item.get("url"),
            images=_extract_images(item),
            operatingHours=item.get("operatingHours", []),
            addresses=_extract_addresses(item),
            contacts=_extract_contacts(item)
        ))
    return results

def parse_nps_webcams(response: Dict[str, Any]) -> List[Webcam]:
    data_list = response.get("data", [])
    results = []
    for item in data_list:
        # Flatten related parks to a list of codes
        related = [p.get("parkCode") for p in item.get("relatedParks", []) if p.get("parkCode")]
        
        # Determine best image URL (some cams have a 'url' for the page and separate image)
        # Note: NPS webcam structure varies. 'url' is usually the page.
        # We look for an image in the 'images' list if available.
        imgs = _extract_images(item)
        image_url = imgs[0].url if imgs else None

        results.append(Webcam(
            id=item.get("id", ""),
            title=item.get("title", "Unknown Webcam"),
            description=item.get("description", ""),
            url=item.get("url", ""),
            imageUrl=image_url,
            isStreaming=item.get("isStreaming", False),
            status=item.get("status", "Active"),
            relatedParks=related
        ))
    return results

def parse_nps_places(response: Dict[str, Any]) -> List[Place]:
    data_list = response.get("data", [])
    results = []
    for item in data_list:
        results.append(Place(
            id=item.get("id", ""),
            title=item.get("title", "Unknown Place"),
            listingDescription=item.get("listingDescription"),
            bodyText=item.get("bodyText"),
            location=_extract_geo(item),
            images=_extract_images(item),
            # tags=item.get("tags", []),
            amenities=item.get("amenities", []),
            isOpenToPublic=item.get("isOpenToPublic", True),
            isManagedByNps=item.get("isManagedByNps", True)
        ))
    return results

def parse_nps_things_to_do(response: Dict[str, Any]) -> List[ThingToDo]:
    data_list = response.get("data", [])
    results = []
    for item in data_list:
        results.append(ThingToDo(
            id=item.get("id", ""),
            title=item.get("title", "Unknown Activity"),
            shortDescription=item.get("shortDescription", ""),
            longDescription=item.get("longDescription"),
            location=_extract_geo(item),
            duration=item.get("duration"),
            season=item.get("season", []),
            activities=item.get("activities", []),
            arePetsPermitted=item.get("arePetsPermitted", False),
            images=_extract_images(item),
            isReservationRequired=item.get("isReservationRequired", False)
        ))
    return results

def parse_nps_passport_stamps(response: Dict[str, Any]) -> List[PassportStamp]:
    data_list = response.get("data", [])
    results = []
    for item in data_list:
        # Extract park code if available in nested structure
        parks = item.get("parks", [])
        p_code = parks[0].get("parkCode") if parks else None

        results.append(PassportStamp(
            id=item.get("id", ""),
            label=item.get("label", "Unknown Stamp"),
            type=item.get("type", "Physical"),
            parkCode=p_code
        ))
    return results
