import logging
import os
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

from app.clients.nps_client import NPSClient
from app.clients.weather_client import WeatherClient
from app.clients.external_client import ExternalClient
from app.engine.constraints import ConstraintEngine, SafetyStatus, UserPreference
from app.models import TrailSummary, ParkContext, ThingToDo, Event, Campground, VisitorCenter, Webcam, Amenity
from app.services.llm_service import LLMService, LLMResponse, LLMParsedIntent
from app.utils.geospatial import mine_entrances 
from app.services.data_manager import DataManager
from app.services.review_scraper import ReviewScraper

logger = logging.getLogger(__name__)

class SessionContext(BaseModel):
    current_park_code: Optional[str] = None
    current_user_prefs: UserPreference = Field(default_factory=UserPreference)
    current_itinerary: Optional[str] = None
    chat_history: List[str] = Field(default_factory=list)

class OrchestratorRequest(BaseModel):
    user_query: str
    session_context: SessionContext = Field(default_factory=SessionContext)

class OrchestratorResponse(BaseModel):
    chat_response: LLMResponse
    parsed_intent: LLMParsedIntent
    updated_context: SessionContext
    park_context: Optional[ParkContext] = None
    vetted_trails: List[TrailSummary] = []
    vetted_things: List[ThingToDo] = []

class OutdoorConciergeOrchestrator:
    def __init__(
        self,
        llm_service: LLMService,
        nps_client: NPSClient,
        weather_client: WeatherClient,
        external_client: ExternalClient, 
        # DataManager doesn't need to be injected if it's stateless config, 
        # but good practice to initialize it here.
    ):
        self.llm = llm_service
        self.nps = nps_client
        self.weather = weather_client
        self.external = external_client
        self.engine = ConstraintEngine()
        self.data_manager = DataManager() # Initialize Data Manager
        self.review_scraper = ReviewScraper(self.llm) # Initialize Review Scraper (using same LLM service)

    def get_park_amenities(self, park_code: str) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Retrieves amenities from the STATIC CACHE (File System).
        Does NOT trigger live API calls.
        
        Returns:
            {
                "Entrance Name": {
                    "gas station...": [ {...}, ... ],
                    "urgent care...": [ ... ]
                }
            }
        """
        if self.data_manager:
            consolidated = self.data_manager.load_consolidated_amenities(park_code)
            if consolidated and "hubs" in consolidated:
                logger.debug(f"Loaded consolidated amenities for {park_code}")
                results = {}
                for hub_name, hub_data in consolidated["hubs"].items():
                    # 1. Prepare Amenities
                    amenities = hub_data.get("amenities", {})
                    
                    # 2. Inject Park Entrance (Hub Location)
                    loc = hub_data.get("location", {})
                    if "lat" in loc and "lon" in loc:
                         if "Park Entrance" not in amenities:
                             amenities["Park Entrance"] = []
                         
                         amenities["Park Entrance"].insert(0, {
                            "name": hub_name,
                            "type": "entrance",
                            "address": "N/A",
                            "latitude": loc["lat"],
                            "longitude": loc["lon"],
                            "rating": None,
                            "rating_count": None,
                            "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={loc['lat']},{loc['lon']}"
                         })
                    
                    results[hub_name] = amenities
                return results

        # Fallback to legacy mine_entrances logic if no consolidated file
        logger.info(f"Loading cached amenities for {park_code} (FALLBACK)...")
        
        # 1. Fetch raw candidates (NPS Live or Cached - keeping live for now as it's cheap)
        places = self.nps.get_places(park_code)
        vcs = self.nps.get_visitor_centers(park_code)
        
        # 2. Mine Hubs
        places_dicts = [p.model_dump() if hasattr(p, "model_dump") else p for p in places]
        vc_dicts = [v.model_dump() if hasattr(v, "model_dump") else v for v in vcs]
        
        entrances = mine_entrances(park_code, places_dicts, vc_dicts)
        
        # 3. Load from Disk
        results = {}
        for ent in entrances:
            name = ent["name"]
            
            # READ ONLY operation
            data = self.data_manager.load_amenities(park_code, name) or {}
            
            # ALWAYS inject the Entrance itself as an amenity so it appears on map/list
            # Use a special category "Park Entrance"
            if "Park Entrance" not in data:
                data["Park Entrance"] = []
            
            # Check if we already have it (unlikely if empty) or just append
            # Create Amenity for the Hub itself
            hub_amenity = {
                "name": name,
                "type": "entrance",
                "address": "N/A",
                "latitude": ent["lat"],
                "longitude": ent["lon"],
                "rating": None,
                "rating_count": None,
                "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={ent['lat']},{ent['lon']}"
            }
            data["Park Entrance"].insert(0, hub_amenity)

            results[name] = data

        return results

    def handle_query(self, request: OrchestratorRequest) -> OrchestratorResponse:
        # ... (Existing logic unchanged for now) ...
        query = request.user_query
        ctx = request.session_context
        logger.info(f"Orchestrating query: {query}")

        # 1. Parse Intent
        intent = self.llm.parse_user_intent(query)

        # 2. Context Merge
        final_park_code = intent.park_code if intent.park_code else ctx.current_park_code
        updated_context = ctx.model_copy()
        updated_context.current_park_code = final_park_code
        updated_context.current_user_prefs = intent.user_prefs
        updated_context.chat_history.append(f"User: {query}")

        if not final_park_code:
            empty_safety = SafetyStatus(status="Unknown", reason=["No park specified."])
            resp = self.llm.generate_response(
                query=query,
                intent=intent,
                safety=empty_safety,
                chat_history=updated_context.chat_history,
                trails=[], things_to_do=[], events=[], campgrounds=[], visitor_centers=[], webcams=[], amenities=[]
            )
            updated_context.chat_history.append(f"Agent: {resp.message}")
            updated_context.chat_history.append(f"Agent: {resp.message}")
            return OrchestratorResponse(chat_response=resp, parsed_intent=intent, updated_context=updated_context.model_dump())

        intent.park_code = final_park_code

        # 3. Fetch Data (Hybrid approach: Cache-First for static, Live for dynamic)
        
        # --- A. Static Data (Try Local Fixtures First) ---
        park_raw = self.data_manager.load_fixture(intent.park_code, "park_details.json")
        if park_raw:
            park = ParkContext(**park_raw)
            logger.debug(f"Loaded park_details from fixture for {intent.park_code}")
        else:
            park = self.nps.get_park_details(intent.park_code)

        campgrounds_raw = self.data_manager.load_fixture(intent.park_code, "campgrounds.json")
        if campgrounds_raw:
            campgrounds = [Campground(**c) for c in campgrounds_raw]
            logger.debug(f"Loaded campgrounds from fixture for {intent.park_code}")
        else:
            campgrounds = self.nps.get_campgrounds(intent.park_code)

        visitor_centers_raw = self.data_manager.load_fixture(intent.park_code, "visitor_centers.json")
        if visitor_centers_raw:
            visitor_centers = [VisitorCenter(**v) for v in visitor_centers_raw]
            logger.debug(f"Loaded visitor_centers from fixture for {intent.park_code}")
        else:
            visitor_centers = self.nps.get_visitor_centers(intent.park_code)

        webcams_raw = self.data_manager.load_fixture(intent.park_code, "webcams.json")
        if webcams_raw:
            webcams = [Webcam(**w) for w in webcams_raw]
            logger.debug(f"Loaded webcams from fixture for {intent.park_code}")
        else:
            webcams = self.nps.get_webcams(intent.park_code)

        things_to_do_raw = self.data_manager.load_fixture(intent.park_code, "things_to_do.json")
        if things_to_do_raw:
            things_to_do = [ThingToDo(**t) for t in things_to_do_raw]
            logger.debug(f"Loaded things_to_do from fixture for {intent.park_code}")
        else:
            things_to_do = self.nps.get_things_to_do(intent.park_code)

        # --- B. Dynamic Data (Always Live) ---
        alerts = self.nps.get_alerts(intent.park_code)
        events = self.nps.get_events(intent.park_code)
        
        weather = None
        if park and park.location:
            weather = self.weather.get_forecast(intent.park_code, park.location.lat, park.location.lon)

        # Amenities (Checking Hub Cache First)
        amenities_data = self.get_park_amenities(intent.park_code)
        # Flatten amenities from all hubs for LLM context
        amenities = []
        for hub_name, entries in amenities_data.items():
            for category, items in entries.items():
                for item in items:
                    # Construct simple Amenity object for LLM context
                    amenities.append(Amenity(**item))

        # 4. Engine Execution
        # We need _fetch_trails_for_park logic to be real or mock
        raw_trails = self._fetch_trails_for_park(intent.park_code)
        # Initial vetting for fallback logic
        vetted_trails = self.engine.filter_trails(raw_trails, intent.user_prefs)
        
        # 4a. On-Demand Reviews (JIT Enrichment)
        # If user asked for reviews, or asking specific questions about trails, we fetch review data
        if intent.response_type == "reviews" or intent.review_targets:
            logger.info(f"Checking reviews for: {intent.review_targets}")
            # If explicit targets used, scrape them
            targets = intent.review_targets
            if not targets and intent.response_type == "reviews":
                 # Fallback: if "reviews for top 3" etc, we might need logic to pick top 3 vetted trails
                 # For now, let's just pick the top 3 vetted trails if no specific target
                 targets = [t.name for t in vetted_trails[:3]]

            for target in targets:
                try:
                    logger.info(f"Triggering Review Scraper for {target}")
                    self.review_scraper.fetch_reviews(intent.park_code, target)
                except Exception as e:
                     logger.error(f"Review scrape failed for {target}: {e}")
            
            # CRITICAL: Re-fetch trails because fetch_reviews updates the JSON cache we read from!
            raw_trails = self._fetch_trails_for_park(intent.park_code)
            # Re-vet to get updated objects
            vetted_trails = self.engine.filter_trails(raw_trails, intent.user_prefs)

        safety = self.engine.analyze_safety(weather, alerts)
        vetted_trails = self.engine.filter_trails(raw_trails, intent.user_prefs)

        # 5. Response
        chat_resp = self.llm.generate_response(
            query=query,
            intent=intent,
            safety=safety,
            chat_history=updated_context.chat_history,
            trails=vetted_trails,
            things_to_do=things_to_do,
            events=events,
            campgrounds=campgrounds,
            visitor_centers=visitor_centers,
            webcams=webcams,
            amenities=amenities
        )

        updated_context.chat_history.append(f"Agent: {chat_resp.message}")
        updated_context.current_itinerary = chat_resp.message

        return OrchestratorResponse(
            chat_response=chat_resp,
            parsed_intent=intent,
            updated_context=updated_context.model_dump(),
            park_context=park,
            vetted_trails=vetted_trails,
            vetted_things=things_to_do
        )

    def _fetch_trails_for_park(self, park_code: str) -> List[TrailSummary]:
        """
        Loads trail data from the filesystem (trails_v2.json), falling back to mock ONLY if files missing.
        """
        # 1. Try Loading Real Data
        raw_list = self.data_manager.load_fixture(park_code, "trails_v2.json")
        if raw_list:
            try:
                # Convert raw dicts to TrailSummary objects
                # Note: TrailSummary might need to handle extra fields gracefully or we ignore them
                trails = []
                for item in raw_list:
                    # Basic mapping or direct unpacking if schema aligns
                    # Ensure required fields exist or have defaults
                    try:
                        t = TrailSummary(**item)
                        trails.append(t)
                    except Exception as e:
                        # Log but continue so one bad record doesn't break all
                        # logger.warning(f"Failed to parse trail {item.get('name')}: {e}")
                        pass
                        
                    # SELF-HEALING: If average_rating is 0 but we have reviews, calculate it!
                    if t.average_rating == 0 and t.recent_reviews:
                        avg = sum(r.rating for r in t.recent_reviews) / len(t.recent_reviews)
                        t.average_rating = round(avg, 1)
                        t.total_reviews = len(t.recent_reviews)
                        logger.info(f"Self-healed rating for {t.name}: {t.average_rating} ({t.total_reviews} reviews)")
                
                if trails:
                    logger.info(f"Loaded {len(trails)} real trails for {park_code}")
                    return trails

            except Exception as e:
                logger.error(f"Error parsing trails_v2.json for {park_code}: {e}")

        # 2. Fallback Mock Logic
        logger.warning(f"Using MOCK trails for {park_code} (Data Missing)")
        defaults = [
            TrailSummary(
                name=f"Big {park_code.upper()} Loop",
                parkCode=park_code, difficulty="hard", length_miles=12.5, elevation_gain_ft=3000,
                route_type="loop", average_rating=4.8, total_reviews=120, description="Challenging.",
                features=["scenic"], surface_types=["rocky"]
            )
        ]
        if park_code == "yose":
            defaults.append(TrailSummary(name="Mist Trail", parkCode="yose", difficulty="hard", length_miles=6.0, elevation_gain_ft=2000, route_type="out and back", average_rating=4.9, total_reviews=5000, description="Waterfall.", features=["scenic"], surface_types=["steps"]))
        return defaults
