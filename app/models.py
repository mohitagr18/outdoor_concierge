from typing import List, Optional, Dict, Any
import re
from pydantic import BaseModel, Field, model_validator

# --- Common Enums/Types ---
class GeoLocation(BaseModel):
    lat: float
    lon: float

class ParkImage(BaseModel):
    url: str
    title: Optional[str] = None
    altText: Optional[str] = None
    caption: Optional[str] = None
    credit: Optional[str] = None

class ParkContact(BaseModel):
    phoneNumbers: List[Dict[str, str]] = []
    emailAddresses: List[Dict[str, str]] = []

class AmenityInfo(BaseModel):
    """Used in Places, VisitorCenters, Campgrounds"""
    amenities: List[str] = [] # Simplified list of amenity names

class Address(BaseModel):
    line1: Optional[str] = None
    line2: Optional[str] = None
    line3: Optional[str] = None
    city: Optional[str] = None
    stateCode: Optional[str] = None
    postalCode: Optional[str] = None
    type: Optional[str] = "Physical"

class Campground(BaseModel):
    id: str
    name: str
    description: str
    location: Optional[GeoLocation] = None
    campsites: Dict[str, str] = {} # e.g. {"totalSites": "100", "tentOnly": "50"}
    accessibility: Dict[str, Any] = {} # Descriptive text
    amenities: Dict[str, Any] = {}
    contacts: ParkContact = Field(default_factory=ParkContact)
    fees: List[Dict[str, Any]] = []
    images: List[ParkImage] = []
    reservationUrl: Optional[str] = None
    isOpen: bool = True # Inferred or explicit

class VisitorCenter(BaseModel):
    id: str
    name: str
    description: str
    location: Optional[GeoLocation] = None
    url: Optional[str] = None
    images: List[ParkImage] = []
    operatingHours: List[Dict[str, Any]] = []
    addresses: List[Address] = []
    contacts: ParkContact = Field(default_factory=ParkContact)

class Webcam(BaseModel):
    id: str
    title: str
    description: str
    url: str # The page URL
    imageUrl: Optional[str] = None # The specific stream/image URL if available
    isStreaming: bool = False
    status: str = "Active"
    relatedParks: List[str] = [] # List of park codes

class Place(BaseModel):
    id: str
    title: str
    listingDescription: Optional[str] = None
    bodyText: Optional[str] = None
    location: Optional[GeoLocation] = None
    images: List[ParkImage] = []
    amenities: List[str] = []
    isOpenToPublic: bool = True
    isManagedByNps: bool = True
    url: Optional[str] = None

    @model_validator(mode='after')
    def extract_url_from_body(self):
        if not self.url and self.bodyText:
            # Look for the first http(s) link in an href attribute
            match = re.search(r'href=["\'](http[^"\']+)["\']', self.bodyText)
            if match:
                self.url = match.group(1)
        return self

class ThingToDo(BaseModel):
    id: str
    title: str
    shortDescription: str
    longDescription: Optional[str] = None
    location: Optional[GeoLocation] = None
    duration: Optional[str] = None # e.g. "1-2 hours"
    season: List[str] = []
    activities: List[Dict[str, str]] = [] # e.g. [{"name": "Hiking"}]
    arePetsPermitted: bool = False
    images: List[ParkImage] = []
    isReservationRequired: bool = False
    doFeesApply: bool = False
    tags: List[str] = []

class PassportStamp(BaseModel):
    id: str
    label: str # The text on the stamp
    type: str  # e.g. "Physical" or "Virtual"
    parkCode: Optional[str] = None

class Alert(BaseModel):
    id: str
    parkCode: str
    title: str
    description: str
    category: str
    url: Optional[str] = None
    lastIndexedDate: str

class Event(BaseModel):
    title: str
    description: str
    date_start: str
    date_end: Optional[str] = None
    is_free: bool = False
    location: Optional[str] = None
    times: List[Dict[str, Any]] = []
    # NEW FIELDS
    images: List[ParkImage] = []
    dates: List[str] = []     # List of specific dates this event occurs
    tags: List[str] = []      # e.g. ["ranger talk", "family"]
    types: List[str] = []     # e.g. ["Talk", "Gathering"]
    fee_info: Optional[str] = None


class ParkContext(BaseModel):
    """
    Derived from NPS 'parks' endpoint (parks_search.json).
    Now expanded to hold child entities.
    """
    parkCode: str
    fullName: str
    description: str
    location: GeoLocation
    contacts: ParkContact = Field(default_factory=ParkContact)
    operatingHours: List[Dict[str, Any]] = []
    url: str
    images: List[ParkImage] = []
    
    # NEW: Lists of child entities
    campgrounds: List[Campground] = []
    visitor_centers: List[VisitorCenter] = []
    webcams: List[Webcam] = []
    places: List[Place] = []
    things_to_do: List[ThingToDo] = []
    passport_stamps: List[PassportStamp] = []

# --- Weather & Trail Models (Unchanged) ---
class DailyForecast(BaseModel):
    date: str
    maxtemp_f: float
    mintemp_f: float
    avgtemp_f: float
    daily_chance_of_rain: int
    condition: str
    uv: float

class WeatherSummary(BaseModel):
    parkCode: str
    current_temp_f: float
    current_condition: str
    wind_mph: float = 0.0
    humidity: int = 0
    forecast: List[DailyForecast]
    sunrise: Optional[str] = None
    sunset: Optional[str] = None
    weather_alerts: List[Dict[str, Any]] = []

class TrailReview(BaseModel):
    author: str
    rating: int
    date: str
    text: str
    condition_tags: List[str] = []
    visible_image_urls: List[str] = []

class TrailSummary(BaseModel):
    name: str
    parkCode: Optional[str] = None
    difficulty: Optional[str] = "moderate" # Default if missing
    length_miles: Optional[float] = 0.0
    elevation_gain_ft: Optional[int] = 0
    route_type: Optional[str] = "out and back"
    average_rating: Optional[float] = None
    total_reviews: Optional[int] = 0
    description: Optional[str] = ""
    features: List[str] = []
    surface_types: List[str] = []
    surface_types: List[str] = []
    recent_reviews: List[TrailReview] = []
    images: List[ParkImage] = []  # NEW: Trail images from NPS data
    
    # Fields for URL support
    nps_url: Optional[str] = None
    alltrails_url: Optional[str] = None

    @property
    def url(self) -> Optional[str]:
        """Returns the best available URL for the LLM context."""
        return self.nps_url or self.alltrails_url

    @model_validator(mode='after')
    def set_defaults(self):
        if not self.difficulty:
            self.difficulty = "moderate"
        if not self.route_type:
            self.route_type = "out and back"
        if self.length_miles is None:
            self.length_miles = 0.0
        if self.elevation_gain_ft is None:
            self.elevation_gain_ft = 0
        if self.average_rating is None:
            self.average_rating = 0.0
        if self.total_reviews is None:
            self.total_reviews = 0
        
        # Ensure lists are never None
        if self.features is None: self.features = []
        if self.surface_types is None: self.surface_types = []
        if self.recent_reviews is None: self.recent_reviews = []
        if self.images is None: self.images = []
        
        return self

class Amenity(BaseModel):
    name: str
    type: str = "amenity"
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    open_now: Optional[bool] = None
    google_maps_url: Optional[str] = None
    image_url: Optional[str] = None

class PhotoSpot(BaseModel):
    name: str
    parkCode: str
    description: str
    best_time_of_day: List[str] = []
    rank: Optional[int] = None                  # Needs to be optional for backward compatibility
    best_seasons: List[str] = Field(default_factory=list) # e.g. ["Summer", "Fall"]
    source_url: Optional[str] = None            # Link to the blog post
    tips: List[str] = []
    image_url: Optional[str] = None

class ScenicDrive(BaseModel):
    name: str
    parkCode: Optional[str] = None
    description: str
    rank: Optional[int] = None
    distance_miles: Optional[float] = None
    drive_time: Optional[str] = None  # e.g. "2-3 hours"
    highlights: List[str] = []  # Key viewpoints/stops
    best_time: Optional[str] = None  # e.g. "Sunrise", "Any time"
    tips: List[str] = []
    source_url: Optional[str] = None
    image_url: Optional[str] = None
