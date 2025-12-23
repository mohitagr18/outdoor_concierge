from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# --- Common Enums/Types ---
class GeoLocation(BaseModel):
    lat: float
    lon: float

# --- NPS Models (Park Context, Alerts, Events) ---
class ParkImage(BaseModel):
    url: str
    title: Optional[str] = None
    altText: Optional[str] = None
    caption: Optional[str] = None
    credit: Optional[str] = None

class ParkContact(BaseModel):
    phoneNumbers: List[Dict[str, str]] = []
    emailAddresses: List[Dict[str, str]] = []

class ParkContext(BaseModel):
    """
    Derived from NPS 'parks' endpoint (parks_search.json).
    """
    parkCode: str
    fullName: str
    description: str
    location: GeoLocation
    contacts: ParkContact = Field(default_factory=ParkContact)
    operatingHours: List[Dict[str, Any]] = []
    url: str
    images: List[ParkImage] = []

class Alert(BaseModel):
    """
    Derived from NPS 'alerts' endpoint.
    """
    id: str
    parkCode: str
    title: str
    description: str
    category: str
    url: Optional[str] = None
    lastIndexedDate: str

class Event(BaseModel):
    """
    Derived from NPS 'events' endpoint.
    """
    title: str
    description: str
    date_start: str
    date_end: Optional[str] = None
    is_free: bool = False
    location: Optional[str] = None
    times: List[Dict[str, Any]] = []

# --- Weather Models ---
class DailyForecast(BaseModel):
    date: str
    maxtemp_f: float
    mintemp_f: float
    avgtemp_f: float
    daily_chance_of_rain: int
    condition: str
    uv: float

class WeatherSummary(BaseModel):
    """
    Derived from WeatherAPI (weather.json).
    """
    parkCode: str
    current_temp_f: float
    current_condition: str
    forecast: List[DailyForecast]
    sunrise: Optional[str] = None
    sunset: Optional[str] = None
    weather_alerts: List[Dict[str, Any]] = []

# --- Trail Models (AllTrails) ---
class TrailReview(BaseModel):
    author: str
    rating: int
    date: str
    text: str
    condition_tags: List[str] = []
    visible_image_urls: List[str] = []

class TrailSummary(BaseModel):
    """
    Derived from Firecrawl + LLM extraction (scraped_extract_llm.json).
    """
    name: str
    parkCode: Optional[str] = None
    difficulty: str
    length_miles: float
    elevation_gain_ft: int
    route_type: str
    average_rating: float
    total_reviews: int
    description: str
    features: List[str] = []
    surface_types: List[str] = []
    recent_reviews: List[TrailReview] = []

# --- Amenity & Logistics Models ---
class Amenity(BaseModel):
    """
    Derived from Serper (Google Maps) data.
    """
    name: str
    type: str # 'Gas', 'Medical', 'Grocery'
    address: str
    rating: Optional[float] = None
    open_now: Optional[bool] = None
    google_maps_url: str

class PhotoSpot(BaseModel):
    """
    Derived from Photo Blog Scrapes.
    """
    name: str
    parkCode: str
    description: str
    best_time_of_day: List[str] = []
    tips: List[str] = []
    image_url: Optional[str] = None
