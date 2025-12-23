import logging
import os
from typing import List, Optional

from pydantic import BaseModel, Field

from app.clients.nps_client import NPSClient
from app.clients.weather_client import WeatherClient
from app.clients.external_client import ExternalClient
from app.engine.constraints import ConstraintEngine, SafetyStatus, UserPreference
from app.models import TrailSummary, ParkContext, ThingToDo, Event, Campground, VisitorCenter, Webcam, Amenity
from app.services.llm_service import LLMService, LLMResponse, LLMParsedIntent

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
        external_client: ExternalClient, # NEW Dependency
    ):
        self.llm = llm_service
        self.nps = nps_client
        self.weather = weather_client
        self.external = external_client
        self.engine = ConstraintEngine()

    def handle_query(self, request: OrchestratorRequest) -> OrchestratorResponse:
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
                trails=[], things_to_do=[], events=[], campgrounds=[], visitor_centers=[], webcams=[], amenities=[]
            )
            updated_context.chat_history.append(f"Agent: {resp.message}")
            return OrchestratorResponse(chat_response=resp, parsed_intent=intent, updated_context=updated_context)

        intent.park_code = final_park_code

        # 3. Fetch Data (All Sources)
        park = self.nps.get_park_details(intent.park_code)
        alerts = self.nps.get_alerts(intent.park_code)
        
        # NPS Rich Data
        things_to_do = self.nps.get_things_to_do(intent.park_code)
        events = self.nps.get_events(intent.park_code)
        campgrounds = self.nps.get_campgrounds(intent.park_code)
        visitor_centers = self.nps.get_visitor_centers(intent.park_code)
        webcams = self.nps.get_webcams(intent.park_code)

        weather = None
        if park and park.location:
            weather = self.weather.get_forecast(intent.park_code, park.location.lat, park.location.lon)

        # External Amenities (Serper)
        amenities = []
        if park and park.location:
            # We assume ExternalClient has get_amenities(lat, lon, query="amenities")
            # Or you might map 'amenities' to generic queries like 'food', 'gas' if needed.
            # For now, let's assume a generic fetch or empty if not implemented yet.
            amenities = self.external.get_amenities("amenities",park.location.lat, park.location.lon)

        raw_trails = self._fetch_trails_for_park(intent.park_code)

        # 4. Engine Execution
        safety = self.engine.analyze_safety(weather, alerts)
        vetted_trails = self.engine.filter_trails(raw_trails, intent.user_prefs)
        
        # 5. Response
        chat_resp = self.llm.generate_response(
            query=query,
            intent=intent,
            safety=safety,
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
            updated_context=updated_context,
            park_context=park,
            vetted_trails=vetted_trails,
            vetted_things=things_to_do
        )

    def _fetch_trails_for_park(self, park_code: str) -> List[TrailSummary]:
        # Mock logic as before
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
