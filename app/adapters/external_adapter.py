from typing import Dict, Any, List
from app.models import Amenity, PhotoSpot

def parse_amenity_place(place_json: Dict[str, Any], amenity_type: str) -> Amenity:
    """
    Parses a single 'place' object from Serper API output.
    """
    # Construct Google Maps Link if missing
    cid = place_json.get("cid")
    if cid:
        map_url = f"https://maps.google.com/?cid={cid}"
    else:
        # Fallback if no CID (simplified for robustness)
        map_url = "https://www.google.com/maps"

    return Amenity(
        name=place_json.get("title", "Unknown Place"),
        type=amenity_type,
        address=place_json.get("address", ""),
        rating=place_json.get("rating"),
        open_now=place_json.get("open_now"), # Serper often returns boolean or missing
        google_maps_url=map_url
    )

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
