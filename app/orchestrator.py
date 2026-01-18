import logging
import os
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

from app.clients.nps_client import NPSClient
from app.clients.weather_client import WeatherClient
from app.clients.external_client import ExternalClient
from app.engine.constraints import ConstraintEngine, SafetyStatus, UserPreference
from app.models import TrailSummary, ParkContext, ThingToDo, Event, Campground, VisitorCenter, Webcam, Amenity, Alert, PhotoSpot, ScenicDrive
from app.services.llm_service import LLMService, LLMResponse, LLMParsedIntent
from app.utils.geospatial import mine_entrances 
from app.services.data_manager import DataManager
from app.services.review_scraper import ReviewScraper
from app.services.park_data_fetcher import ParkDataFetcher
from app.utils.fuzzy_match import fuzzy_match_trail_name

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
        self.data_manager = DataManager()
        self.review_scraper = ReviewScraper(self.llm)
        self.park_fetcher = ParkDataFetcher(nps_client=self.nps, data_manager=self.data_manager)

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

        # 1. Parse Intent (pass current context so LLM doesn't hallucinate park codes)
        intent = self.llm.parse_user_intent(query, current_park_code=ctx.current_park_code)

        # 1b. Normalize Park Code (LLM might return full name like "yosemite" or "glacier" instead of code)
        from app.config import SUPPORTED_PARKS
        
        # Build dynamic reverse lookup from SUPPORTED_PARKS
        # Maps variations like "glacier" -> "glac", "yosemite" -> "yose"
        def build_park_name_map():
            name_map = {}
            first_word_counts = {}  # Track conflicts
            
            # First pass: count first words to detect conflicts
            for code, full_name in SUPPORTED_PARKS.items():
                clean_name = full_name.lower().replace(" national park", "").replace(" national parks", "").strip()
                first_word = clean_name.split()[0] if clean_name else ""
                if first_word and len(first_word) > 3:
                    first_word_counts[first_word] = first_word_counts.get(first_word, 0) + 1
            
            # Second pass: build the map
            for code, full_name in SUPPORTED_PARKS.items():
                # Add the code itself
                name_map[code.lower()] = code
                
                # Add full name without "National Park" suffix
                clean_name = full_name.lower().replace(" national park", "").replace(" national parks", "").strip()
                name_map[clean_name.replace(" ", "")] = code  # "glacierbay" -> "glba"
                name_map[clean_name] = code  # "glacier bay" -> "glba"
                
                # Add first word ONLY if no conflict (e.g., "yosemite" is unique, but "glacier" conflicts)
                first_word = clean_name.split()[0] if clean_name else ""
                if first_word and len(first_word) > 3 and first_word_counts.get(first_word, 0) == 1:
                    name_map[first_word] = code
            
            # Add explicit aliases for commonly used names and conflicts
            name_map["grand canyon"] = "grca"
            name_map["grandcanyon"] = "grca"
            name_map["bryce"] = "brca"
            name_map["smoky mountains"] = "grsm"
            name_map["smokies"] = "grsm"
            name_map["great smokies"] = "grsm"
            name_map["joshua tree"] = "jotr"
            name_map["joshuatree"] = "jotr"
            name_map["death valley"] = "deva"
            name_map["deathvalley"] = "deva"
            name_map["mount rainier"] = "mora"
            name_map["rainier"] = "mora"
            name_map["rocky mountain"] = "romo"
            name_map["rocky mountains"] = "romo"
            name_map["rockymountain"] = "romo"
            
            # Resolve conflicts explicitly (both Glacier and Glacier Bay start with "glacier")
            name_map["glacier"] = "glac"  # Glacier National Park (more commonly searched)
            name_map["glacier bay"] = "glba"
            name_map["glacierbay"] = "glba"
            
            # Grand Teton vs Grand Canyon
            name_map["grand teton"] = "grte"
            name_map["grandteton"] = "grte"
            name_map["teton"] = "grte"
            name_map["tetons"] = "grte"
            
            return name_map
        
        PARK_NAME_TO_CODE = build_park_name_map()
        
        if intent.park_code:
            original = intent.park_code
            # Try exact match first, then cleaned version
            lookup_key = intent.park_code.lower().replace(" ", "")
            normalized = PARK_NAME_TO_CODE.get(lookup_key)
            if not normalized:
                # Try with spaces preserved
                normalized = PARK_NAME_TO_CODE.get(intent.park_code.lower())
            if not normalized:
                # Keep original if no mapping found (might be a valid code already)
                normalized = intent.park_code.lower()
            intent.park_code = normalized
            logger.info(f"Park code normalization: '{original}' -> '{normalized}'")

        # 2. Context Merge
        final_park_code = intent.park_code if intent.park_code else ctx.current_park_code
        updated_context = ctx.model_copy()
        updated_context.current_park_code = final_park_code
        updated_context.current_user_prefs = intent.user_prefs
        updated_context.chat_history.append(f"User: {query}")

        if not final_park_code:
            logger.warning(f"⚠️ No park code available (intent: {intent.park_code}, context: {ctx.current_park_code})")
            
            # Create a friendly response asking user to specify a park
            from app.config import SUPPORTED_PARKS
            park_list = ", ".join([f"**{name}**" for name in SUPPORTED_PARKS.values()])
            ask_park_message = (
                f"I'd love to help! Could you please tell me which park you're interested in? "
                f"I currently support: {park_list}.\n\n"
                f"For example, try asking:\n"
                f"- \"Tell me about Zion\"\n"
                f"- \"What trails are in Bryce Canyon?\"\n"
                f"- \"Plan a trip to Yosemite\""
            )
            
            empty_safety = SafetyStatus(status="Unknown", reason=["No park specified."])
            resp = LLMResponse(
                message=ask_park_message,
                safety_status="Unknown",
                safety_reasons=["No park specified."],
                suggested_trails=[]
            )
            updated_context.chat_history.append(f"Agent: {resp.message}")
            return OrchestratorResponse(chat_response=resp, parsed_intent=intent, updated_context=updated_context.model_dump())
        
        logger.info(f"✅ Using park code: {final_park_code}")

        intent.park_code = final_park_code
        
        # Check if park is supported and has data loaded
        if final_park_code not in SUPPORTED_PARKS:
            # Park is not in our supported list
            park_list = ", ".join([f"**{name}**" for name in SUPPORTED_PARKS.values()])
            unsupported_message = (
                f"I don't have data loaded for that park yet. 🏞️\n\n"
                f"I currently fully support: {park_list}.\n\n"
                f"**Want me to add more parks?** Let me know and I can help extend support!\n\n"
                f"In the meantime, try asking about one of the parks listed above."
            )
            resp = LLMResponse(
                message=unsupported_message,
                safety_status="Unknown",
                safety_reasons=["Park not supported."],
                suggested_trails=[]
            )
            updated_context.chat_history.append(f"Agent: {resp.message}")
            return OrchestratorResponse(chat_response=resp, parsed_intent=intent, updated_context=updated_context.model_dump())
        
        # Check if park has basic data loaded (trails, park details)
        if not self.park_fetcher.has_basic_data(final_park_code):
            park_name = SUPPORTED_PARKS.get(final_park_code, final_park_code.upper())
            no_data_message = (
                f"I'd love to help you explore **{park_name}**! However, I don't have the detailed data loaded yet. 📂\n\n"
                f"**To get started:**\n"
                f"1. Go to the **🔭 Park Explorer** tab\n"
                f"2. Select **{park_name}** from the dropdown\n"
                f"3. Click the **🚀 Fetch Park Data** button\n\n"
                f"Once the data is loaded, come back here and I'll be able to give you detailed trail recommendations, "
                f"conditions, reviews, and more!"
            )
            resp = LLMResponse(
                message=no_data_message,
                safety_status="Unknown",
                safety_reasons=["Park data not loaded."],
                suggested_trails=[]
            )
            updated_context.chat_history.append(f"Agent: {resp.message}")
            return OrchestratorResponse(chat_response=resp, parsed_intent=intent, updated_context=updated_context.model_dump())
        
        # Check for PARTIAL data (basic exists, but explorer-critical files are missing)
        # Build comprehensive check for all data types
        query_lower = query.lower()
        park_name = SUPPORTED_PARKS.get(final_park_code, final_park_code.upper())
        
        # Define data requirements for different query types
        DATA_REQUIREMENTS = {
            "trails": {
                "files": ["trails_v2.json"],
                "keywords": ["trail", "hike", "hiking", "walk", "trek", "plan", "itinerary", "trip", "day"],
                "response_types": ["itinerary", "list_options"],
                "emoji": "🥾",
                "name": "trail data",
                "description": "trail recommendations and itineraries"
            },
            "photos": {
                "files": ["photo_spots.json"],
                "keywords": ["photo", "photography", "picture", "sunrise", "sunset", "shot", "camera", "viewpoint"],
                "response_types": [],
                "emoji": "📸",
                "name": "photo spot data",
                "description": "photography location recommendations"
            },
            "drives": {
                "files": ["scenic_drives.json"],
                "keywords": ["drive", "driving", "road", "scenic", "car", "auto tour", "motor"],
                "response_types": [],
                "emoji": "🚗",
                "name": "scenic drive data",
                "description": "driving tour recommendations"
            },
            "amenities": {
                "files": ["consolidated_amenities.json"],
                "keywords": ["gas", "fuel", "restaurant", "food", "eat", "grocery", "store", "hotel", "lodging", 
                           "rent", "gear", "equipment", "pharmacy", "medical", "urgent", "shop", "amenity", "amenities",
                           "nearby", "where can"],
                "response_types": [],
                "emoji": "🏪",
                "name": "amenity data",
                "description": "nearby services and businesses"
            }
        }
        
        # Check each data type and block if required data is missing
        for data_type, config in DATA_REQUIREMENTS.items():
            files_missing = any(not self.data_manager.has_fixture(final_park_code, f) for f in config["files"])
            
            if not files_missing:
                continue
                
            query_needs_this = (
                intent.response_type in config["response_types"] or
                any(kw in query_lower for kw in config["keywords"])
            )
            
            if query_needs_this:
                missing_data_message = (
                    f"I'd love to help with {config['description']} for **{park_name}**! "
                    f"However, I don't have the {config['name']} loaded yet. {config['emoji']}\n\n"
                    f"**To get this information:**\n"
                    f"1. Go to the **🔭 Park Explorer** tab\n"
                    f"2. Select **{park_name}** from the dropdown\n"
                    f"3. Click the **🚀 Fetch Park Data** button\n\n"
                    f"Once the data is loaded, come back here and I'll be able to provide detailed recommendations!"
                )
                resp = LLMResponse(
                    message=missing_data_message,
                    safety_status="Unknown",
                    safety_reasons=[f"{config['name'].title()} not loaded."],
                    suggested_trails=[]
                )
                updated_context.chat_history.append(f"Agent: {resp.message}")
                return OrchestratorResponse(chat_response=resp, parsed_intent=intent, updated_context=updated_context.model_dump())
        
        # Check for general partial data (for informational notice only)
        EXPLORER_CRITICAL_FILES = ["trails_v2.json", "photo_spots.json", "scenic_drives.json"]
        missing_critical = [f for f in EXPLORER_CRITICAL_FILES if not self.data_manager.has_fixture(final_park_code, f)]
        
        partial_data_notice = ""
        if missing_critical:
            missing_friendly = ", ".join([f.replace("_", " ").replace(".json", "").title() for f in missing_critical])
            partial_data_notice = (
                f"\n\n---\n"
                f"⚠️ **Note:** I have partial data for {park_name}. "
                f"Missing: {missing_friendly}. "
                f"Visit the **🔭 Park Explorer** tab and click **🚀 Fetch Park Data** to load complete information."
            )
            logger.info(f"📊 Partial data detected for {final_park_code}, missing: {missing_critical}")
        
        # --- A. Static Data (Try Local Fixtures First, Save on Fetch) ---
        # Helper to load or fetch and save
        def load_or_fetch(fixture_name, fetch_fn, model_class=None):
            raw = self.data_manager.load_fixture(intent.park_code, fixture_name)
            if raw:
                if model_class:
                    if isinstance(raw, list):
                        return [model_class(**item) for item in raw]
                    return model_class(**raw)
                return raw
            else:
                # Fetch from API and save for next time
                logger.info(f"Fetching {fixture_name} from NPS API for {intent.park_code}...")
                data = fetch_fn(intent.park_code)
                if data:
                    self.data_manager.save_fixture(intent.park_code, fixture_name, data)
                    logger.info(f"Saved {fixture_name} to fixture cache")
                return data
        
        park = load_or_fetch("park_details.json", self.nps.get_park_details, ParkContext)
        campgrounds = load_or_fetch("campgrounds.json", self.nps.get_campgrounds, Campground) or []
        visitor_centers = load_or_fetch("visitor_centers.json", self.nps.get_visitor_centers, VisitorCenter) or []
        webcams = load_or_fetch("webcams.json", self.nps.get_webcams, Webcam) or []
        things_to_do = load_or_fetch("things_to_do.json", self.nps.get_things_to_do, ThingToDo) or []
        
        # Photo spots (static fixture, no API fallback)
        photo_spots_raw = self.data_manager.load_fixture(intent.park_code, "photo_spots.json")
        photo_spots = []
        if photo_spots_raw:
            for ps in photo_spots_raw:
                try:
                    photo_spots.append(PhotoSpot(**ps) if isinstance(ps, dict) else ps)
                except Exception as e:
                    logger.warning(f"Failed to parse photo spot: {e}")
            logger.info(f"Loaded {len(photo_spots)} photo spots for {intent.park_code}")

        # Scenic drives (static fixture, no API fallback)
        scenic_drives_raw = self.data_manager.load_fixture(intent.park_code, "scenic_drives.json")
        scenic_drives = []
        if scenic_drives_raw:
            for sd in scenic_drives_raw:
                try:
                    scenic_drives.append(ScenicDrive(**sd) if isinstance(sd, dict) else sd)
                except Exception as e:
                    logger.warning(f"Failed to parse scenic drive: {e}")
            logger.info(f"Loaded {len(scenic_drives)} scenic drives for {intent.park_code}")


        # --- B. Dynamic Data (Cached Daily) ---
        # 1. Alerts
        alerts_data = self.data_manager.load_daily_cache(intent.park_code, "alerts")
        if alerts_data is not None:
            alerts = [Alert(**a) for a in alerts_data]
            logger.info(f"Using cached alerts for {intent.park_code}")
        else:
            alerts = self.nps.get_alerts(intent.park_code)
            # Save raw dicts
            self.data_manager.save_daily_cache(intent.park_code, "alerts", [a.model_dump() for a in alerts])

        # 2. Events
        events_data = self.data_manager.load_daily_cache(intent.park_code, "events")
        if events_data is not None:
            events = [Event(**e) for e in events_data]
            logger.info(f"Using cached events for {intent.park_code}")
        else:
            events = self.nps.get_events(intent.park_code)
            self.data_manager.save_daily_cache(intent.park_code, "events", [e.model_dump() for e in events])
        
        # 3. Weather
        weather = None
        if park and park.location:
            weather_data = self.data_manager.load_daily_cache(intent.park_code, "weather")
            if weather_data:
                # Need to import WeatherSummary if not already available in scope? 
                # Models are imported at top.
                from app.models import WeatherSummary # Ensure safe import or rely on top-level
                try:
                    weather = WeatherSummary(**weather_data)
                    logger.info(f"Using cached weather for {intent.park_code}: {weather.current_temp_f}F")
                except Exception as e:
                    logger.warning(f"Failed to reconstitute cached weather: {e}")
                    weather = None
            else:
                logger.info(f"No daily weather cache found for {intent.park_code}")

            if not weather:
                weather = self.weather.get_forecast(intent.park_code, park.location.lat, park.location.lon)
                if weather:
                    self.data_manager.save_daily_cache(intent.park_code, "weather", weather.model_dump())

        # Amenities (Checking Hub Cache First)
        amenities_data = self.get_park_amenities(intent.park_code)
        # Flatten amenities from all hubs for LLM context, preserving category
        amenities = []
        for hub_name, entries in amenities_data.items():
            for category, items in entries.items():
                for item in items:
                    # Add category to item for LLM context
                    item_with_category = {**item, "category": category}
                    # Construct simple Amenity object for LLM context
                    try:
                        amenities.append(Amenity(**item_with_category))
                    except Exception:
                        # If Amenity model doesn't have category field, just use original
                        amenities.append(Amenity(**item))

        # 4. Engine Execution
        # We need _fetch_trails_for_park logic to be real or mock
        raw_trails = self._fetch_trails_for_park(intent.park_code)
        
        # DEFAULT: Vetted trails (Strict)
        vetted_trails = self.engine.filter_trails(raw_trails, intent.user_prefs)

        # 4a. On-Demand Reviews (JIT Enrichment)
        # If user asked for reviews, or asking specific questions about trails, we fetch review data
        if intent.response_type == "reviews" or intent.review_targets:
            logger.info(f"🔍 REVIEW REQUEST - Intent targets: {intent.review_targets}")
            # If explicit targets used, scrape them
            targets = intent.review_targets
            if not targets and intent.response_type == "reviews":
                 # Fallback: if "reviews for top 3" etc, we might need logic to pick top 3 vetted trails
                 # For now, let's just pick the top 3 vetted trails if no specific target
                 targets = [t.name for t in vetted_trails[:3]]
                 logger.info(f"📋 Using fallback top 3 trails: {targets}")

            logger.info(f"📝 Final scrape targets list: {targets}")
            for target in targets:
                try:
                    logger.info(f"Triggering Review Scraper for {target}")
                    self.review_scraper.fetch_reviews(intent.park_code, target)
                except Exception as e:
                     logger.error(f"Review scrape failed for {target}: {e}")
            
            # UPDATE Intent with effective targets so LLM knows what to focus on
            intent.review_targets = targets
            
            # CRITICAL: Re-fetch trails because fetch_reviews updates the JSON cache we read from!
            raw_trails = self._fetch_trails_for_park(intent.park_code)
            
            # AUTO-TARGETING: Ensure any trail with FRESH reviews is treated as a target
            # This handles cases where user query ("Bridalveil") doesn't match canonical name ("Bridalveil Fall Trailhead") perfectly
            # or when fallback "top trails" logic was used.
            from datetime import datetime, timedelta
            now = datetime.now()
            
            fresh_targets = []
            if intent.review_targets:
                 fresh_targets.extend(intent.review_targets)
                 
            for t in raw_trails:
                if t.recent_reviews:
                    # Check if updated in the last 5 minutes (meaning we just scraped it)
                    # or if we want to be broader, just check if it has reviews and is in the original target list
                    # But the safest bet for "I just scraped this" is the timestamp.
                    # Actually, simplistic approach: match against original targets OR just scraped.
                    
                    # If we just triggered a scrape, t.reviews_last_updated should be very recent.
                    # Let's trust the 'targets' list we iterated over, but match it to canonical names.
                    
                    # Better: If t.name pseudo-matches ANY of the requested targets, verify it's in the final list.
                    # OR, simply: If we requested 'X', and we found reviews for 'X Trailhead', add 'X Trailhead' to targets.
                    
                    # Logic:
                    # 1. If explicit targets were requested, ensure canonical names are in intent
                    passed_through = False
                    if targets:
                         for tgt in targets:
                             if fuzzy_match_trail_name(tgt, t.name):
                                 if t.name not in fresh_targets:
                                     fresh_targets.append(t.name)
                                 passed_through = True
                    
                    # 2. If NO explicit targets (fallback case), add everything with reviews
                    if not targets or (len(targets) >= 3 and "top trails" in query.lower()): # Heuristic for fallback
                         if t.name not in fresh_targets:
                             # Check if fresh (e.g. within last hour)
                             last_up = t.get("reviews_last_updated") if isinstance(t, dict) else getattr(t, "reviews_last_updated", None)
                             # Default to True if valid reviews exist and we are in fallback mode
                             if last_up:
                                 try:
                                     last_dt = datetime.fromisoformat(last_up)
                                     if (now - last_dt) < timedelta(minutes=60):
                                          fresh_targets.append(t.name)
                                 except:
                                     fresh_targets.append(t.name)
                             else:
                                 # If no timestamp but has reviews, include it
                                 fresh_targets.append(t.name)
                         if t.name not in fresh_targets:
                             # verify it's fresh?
                             fresh_targets.append(t.name)
            
            intent.review_targets = fresh_targets
            logger.info(f"✅ RESOLVED Review Targets for LLM Context: {intent.review_targets}")
            
            # DEBUG: Log which trails have reviews
            trails_with_reviews = [t.name for t in raw_trails if t.recent_reviews]
            logger.info(f"📊 Trails in cache with reviews ({len(trails_with_reviews)}): {trails_with_reviews[:10]}")

            # Re-vet to get updated objects
            vetted_trails = self.engine.filter_trails(raw_trails, intent.user_prefs)

        safety = self.engine.analyze_safety(weather, alerts)
        
        # RELAXATION LOGIC: 
        # For General Chat / Entity Lookup / Broad Reviews -> Use ALL RAW TRAILS (or minimal filter)
        # This ensures "Tell me about Pa'rus" works even if Pa'rus is rating < 3.5
        if intent.response_type in ["general_chat", "entity_lookup", "reviews"]:
             if not intent.user_prefs or intent.user_prefs == UserPreference():
                 # Only relax if user didn't explicitly set preferences (like "easy trails")
                 # Actually, even for general chat, we want to show everything unless constraints are explicit.
                 # Let's trust raw_trails is better for "context" in these modes.
                 vetted_trails = raw_trails
        
        # Else (Itinerary / List Options): Keep strict vetted_trails logic above

        # 5. Response
        logger.info(f"📤 CALLING LLM with {len(vetted_trails)} trails, response_type={intent.response_type}, review_targets={intent.review_targets}")
        if intent.response_type == "reviews":
            trail_names = [t.name for t in vetted_trails]
            logger.info(f"📋 Trail names being sent: {trail_names[:10]}")
        
        chat_resp = self.llm.generate_response(
            query=query,
            intent=intent,
            safety=safety,
            weather=weather,
            alerts=alerts,
            chat_history=updated_context.chat_history,
            trails=vetted_trails,
            things_to_do=things_to_do,
            events=events,
            campgrounds=campgrounds,
            visitor_centers=visitor_centers,
            webcams=webcams,
            amenities=amenities,
            photo_spots=photo_spots,
            scenic_drives=scenic_drives
        )

        # Append partial data notice if applicable
        if partial_data_notice:
            chat_resp.message = chat_resp.message + partial_data_notice

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
