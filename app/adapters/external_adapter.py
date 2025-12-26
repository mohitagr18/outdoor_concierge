from typing import List, Dict, Any
from app.models import Amenity

def parse_serper_amenities(data: Dict[str, Any]) -> List[Amenity]:
    """
    Parses raw Serper JSON into Amenity models.
    """
    results = []
    if not data or "places" not in data:
        return results

    for item in data["places"]:
        try:
            # Safely extract Lat/Lon
            lat = item.get("latitude")
            lon = item.get("longitude")
            
            amenity = Amenity(
                name=item.get("title", "Unknown"),
                type=item.get("type") or (item.get("types", [])[0] if item.get("types") else "amenity"),
                address=item.get("address", "Unknown Address"),
                latitude=float(lat) if lat is not None else None,
                longitude=float(lon) if lon is not None else None,
                rating=item.get("rating"),
                rating_count=item.get("ratingCount"),
                website=item.get("website"),
                phone=item.get("phoneNumber"),
                # Cid to Maps URL logic
                google_maps_url=f"https://www.google.com/maps/place/?q=place_id:{item.get('cid')}" if item.get("cid") else None,
                image_url=item.get("thumbnailUrl")
            )
            results.append(amenity)
        except Exception:
            continue
    return results
