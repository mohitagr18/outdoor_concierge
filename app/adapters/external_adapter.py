from typing import List, Dict, Any
from app.models import Amenity, PhotoSpot

def parse_serper_amenities(response_json: Dict[str, Any]) -> List[Amenity]:
    """
    Parses the 'places' list from a Serper.dev API response.
    """
    places = response_json.get("places", [])
    amenities = []

    for place in places:
        # Construct Google Maps Link if missing
        cid = place.get("cid")
        if cid:
            map_url = f"https://maps.google.com/?cid={cid}"
        else:
            map_url = "https://www.google.com/maps"

        amenities.append(Amenity(
            name=place.get("title", "Unknown Place"),
            type=place.get("category", "Unknown"),
            address=place.get("address", ""),
            rating=float(place.get("rating", 0.0) or 0.0),
            open_now=place.get("open_now"), # Serper often doesn't give a simple boolean for this
            google_maps_url=map_url
        ))
    return amenities

def parse_photo_spot(spot_json: Dict[str, Any], park_code: str) -> PhotoSpot:
    """
    Parses a photo spot entry from our Firecrawl blog scrape.
    """
    return PhotoSpot(
        name=spot_json.get("name", "Unknown Spot"),
        parkCode=park_code,
        description=spot_json.get("description", ""),
        best_time_of_day=spot_json.get("best_time_of_day", []),
        tips=spot_json.get("tips", []),
        image_url=spot_json.get("image_url")
    )
