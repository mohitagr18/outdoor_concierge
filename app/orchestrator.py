import logging
import os
from typing import List, Optional

from pydantic import BaseModel, Field

from app.clients.nps_client import NPSClient
from app.clients.weather_client import WeatherClient
from app.engine.constraints import ConstraintEngine, SafetyStatus, UserPreference
from app.models import TrailSummary, ParkContext, ThingToDo, Event
from app.services.llm_service import LLMService, LLMResponse, LLMParsedIntent

logger = logging.getLogger(__name__)


# --- New Context Models ---

class SessionContext(BaseModel):
    """
    Represents the state held by the client (Streamlit).
    Passed into the Orchestrator to resolve follow-up queries.
    """
    current_park_code: Optional[str] = None
    current_user_prefs: UserPreference = Field(default_factory=UserPreference)
    current_itinerary: Optional[str] = None
    chat_history: List[str] = Field(default_factory=list)  # Simple list of past messages


class OrchestratorRequest(BaseModel):
    user_query: str
    session_context: SessionContext = Field(default_factory=SessionContext)


class OrchestratorResponse(BaseModel):
    chat_response: LLMResponse
    parsed_intent: LLMParsedIntent
    updated_context: SessionContext  # Return the new state to the client
    park_context: Optional[ParkContext] = None
    vetted_trails: List[TrailSummary] = []
    vetted_things: List[ThingToDo] = []


class OutdoorConciergeOrchestrator:
    def __init__(
        self,
        llm_service: LLMService,
        nps_client: NPSClient,
        weather_client: WeatherClient,
    ):
        self.llm = llm_service
        self.nps = nps_client
        self.weather = weather_client
        self.engine = ConstraintEngine()

    def handle_query(self, request: OrchestratorRequest) -> OrchestratorResponse:
        query = request.user_query
        ctx = request.session_context
        logger.info(f"Orchestrating query: {query}")
        logger.info(f"Incoming Context: Park={ctx.current_park_code}, Prefs={ctx.current_user_prefs}")

        # --- 1. Parse Intent ---
        # TODO: In Phase 4, we might pass chat_history to the LLM here for better understanding.
        intent = self.llm.parse_user_intent(query)
        logger.info(f"Raw Intent parsed: {intent.park_code} (Days: {intent.duration_days})")

        # --- 2. Context Merging (The "Brain") ---
        # A. Resolve Park Code
        final_park_code = intent.park_code if intent.park_code else ctx.current_park_code
        
        # B. Resolve Preferences (Merge old + new)
        # If the user specifies new prefs (e.g. "dog friendly"), it overrides/adds to old ones.
        # This is a simple merge strategy; complex logic can be added later.
        merged_prefs = ctx.current_user_prefs.model_copy()
        
        # Update fields only if they are explicitly set in the new intent
        # (Since our LLM service defaults fields, we might need a smarter diff in the future.
        # For now, we trust the LLM's output or just overwrite if it seems intentional.)
        # Actually, LLMService returns a full UserPreference object with defaults.
        # To merge correctly, we'd need to know what was *explicitly* said.
        # For this step, we'll assume the NEW intent is the primary source of truth for prefs
        # IF specific keywords were found. But preserving 'dog_friendly' from previous turn is key.
        
        # Simple heuristic: If the new query is short ("what about tomorrow?"), 
        # keep old prefs. If it changes constraints ("actually no dogs"), update.
        # This is hard to perfect without 'explicit' flags.
        # Let's use the new intent as the base, but if park_code was missing, 
        # we assume it's a follow-up and might want to keep other context.
        
        if not intent.park_code and ctx.current_park_code:
            # It's likely a follow-up. Keep old prefs unless new ones seem specific.
            # (Simplification: just use the accumulated prefs from context for now,
            # unless we detect a conflict. Let's just use the NEW intent's prefs
            # assuming the LLM parsed the *current* desire correctly).
            # WAIT: If I say "Yosemite", then "What about trails?", the second query
            # has no park code. The LLM might return default prefs.
            # We should probably merge:
            pass 
        
        # For Step 3, let's keep it simple:
        # Use new intent prefs. If park code comes from context, use it.
        
        # Update the Context Object for return
        updated_context = ctx.model_copy()
        updated_context.current_park_code = final_park_code
        updated_context.current_user_prefs = intent.user_prefs # Replace for now
        updated_context.chat_history.append(f"User: {query}")

        # If we still have no park, ask for it.
        if not final_park_code:
            empty_safety = SafetyStatus(status="Unknown", reason=["No park specified."])
            resp = self.llm.generate_response(
                query=query,
                intent=intent,
                safety=empty_safety,
                trails=[],
                things_to_do=[],
                events=[]
            )
            updated_context.chat_history.append(f"Agent: {resp.message}")
            return OrchestratorResponse(
                chat_response=resp, 
                parsed_intent=intent, 
                updated_context=updated_context
            )

        # Update Intent with the resolved park code so fetchers work
        intent.park_code = final_park_code

        # --- 3. Fetch Data ---
        park = self.nps.get_park_details(intent.park_code)
        alerts = self.nps.get_alerts(intent.park_code)
        things_to_do = self.nps.get_things_to_do(intent.park_code)
        events = self.nps.get_events(intent.park_code)
        
        weather = None
        if park and park.location:
            weather = self.weather.get_forecast(
                intent.park_code, park.location.lat, park.location.lon
            )

        raw_trails = self._fetch_trails_for_park(intent.park_code)

        # --- 4. Engine ---
        safety = self.engine.analyze_safety(weather, alerts)
        vetted_trails = self.engine.filter_trails(raw_trails, intent.user_prefs)
        vetted_things = things_to_do 

        # --- 5. Response ---
        chat_resp = self.llm.generate_response(
            query=query,
            intent=intent,
            safety=safety,
            trails=vetted_trails,
            things_to_do=vetted_things,
            events=events
        )
        
        updated_context.chat_history.append(f"Agent: {chat_resp.message}")
        updated_context.current_itinerary = chat_resp.message

        return OrchestratorResponse(
            chat_response=chat_resp,
            parsed_intent=intent,
            updated_context=updated_context,
            park_context=park,
            vetted_trails=vetted_trails,
            vetted_things=vetted_things
        )

    def _fetch_trails_for_park(self, park_code: str) -> List[TrailSummary]:
        # Mocking trails for different parks to prove context switching
        defaults = [
             TrailSummary(
                name=f"Big {park_code.upper()} Loop",
                parkCode=park_code,
                difficulty="hard",
                length_miles=12.5,
                elevation_gain_ft=3000,
                route_type="loop",
                average_rating=4.8,
                total_reviews=120,
                description="Challenging loop with views.",
                features=["scenic", "no dogs"],
                surface_types=["rocky"]
            )
        ]
        if park_code == "yose":
            defaults.append(TrailSummary(
                name="Mist Trail",
                parkCode="yose",
                difficulty="hard",
                length_miles=6.0,
                elevation_gain_ft=2000,
                route_type="out and back",
                average_rating=4.9,
                total_reviews=5000,
                description="Iconic waterfall hike.",
                features=["scenic", "no dogs"],
                surface_types=["rocky", "steps"]
            ))
        elif park_code == "grca":
             defaults.append(TrailSummary(
                name="Bright Angel Trail",
                parkCode="grca",
                difficulty="hard",
                length_miles=9.0,
                elevation_gain_ft=3000,
                route_type="out and back",
                average_rating=4.9,
                total_reviews=4000,
                description="Into the canyon.",
                features=["scenic", "water"],
                surface_types=["dirt"]
            ))
            
        return defaults
