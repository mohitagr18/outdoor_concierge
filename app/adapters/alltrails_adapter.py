from typing import Dict, Any, List
from app.models import TrailSummary, TrailReview

def parse_trail_data(trail_json: Dict[str, Any], park_code: str) -> TrailSummary:
    """
    Parses the JSON output from the Firecrawl+LLM scraper into a TrailSummary.
    
    Args:
        trail_json: The dictionary loaded from scraped_extract_llm.json
        park_code: The park code (e.g. 'zion') to associate with this trail.
    """
    # 1. Parse Reviews
    raw_reviews = trail_json.get("recent_reviews", [])
    reviews = []
    for r in raw_reviews:
        reviews.append(TrailReview(
            author=r.get("author", "Anonymous"),
            rating=r.get("rating", 0),
            date=r.get("date", ""),
            text=r.get("text", ""),
            condition_tags=r.get("condition_tags", []),
            visible_image_urls=r.get("visible_image_urls", [])
        ))

    # 2. Parse Trail Summary
    return TrailSummary(
        name=trail_json.get("name", "Unknown Trail"),
        parkCode=park_code,
        difficulty=trail_json.get("difficulty", "Unknown"),
        length_miles=trail_json.get("length_miles", 0.0),
        elevation_gain_ft=trail_json.get("elevation_gain_ft", 0),
        route_type=trail_json.get("route_type", "Unknown"),
        average_rating=trail_json.get("average_rating", 0.0),
        total_reviews=trail_json.get("total_reviews", 0),
        description=trail_json.get("description", ""),
        features=trail_json.get("features", []),
        surface_types=trail_json.get("surface_types", []),
        recent_reviews=reviews
    )
