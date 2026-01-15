from __future__ import annotations

import json
import logging
import os
from typing import List, Optional, Protocol, Literal, Any
from datetime import datetime

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from app.engine.constraints import UserPreference, SafetyStatus
from app.models import TrailSummary, ThingToDo, Event, Campground, VisitorCenter, Webcam, Amenity, TrailReview, PhotoSpot

logger = logging.getLogger(__name__)

# --- Response Types ---
ResponseType = Literal["itinerary", "list_options", "safety_info", "general_chat", "reviews", "entity_lookup"]

# --- DTOs ---
class LLMParsedIntent(BaseModel):
    user_prefs: UserPreference
    park_code: Optional[str] = None
    target_date: Optional[str] = None
    duration_days: int = 1
    response_type: ResponseType = "itinerary"
    review_targets: List[str] = Field(default_factory=list)
    raw_query: str

class LLMResponse(BaseModel):
    message: str
    safety_status: Optional[str] = None
    safety_reasons: List[str] = Field(default_factory=list)
    suggested_trails: List[str] = Field(default_factory=list)
    debug_intent: Optional[LLMParsedIntent] = None

class LLMService(Protocol):
    def parse_user_intent(self, query: str) -> LLMParsedIntent: ...

    def generate_response(
        self,
        *,
        query: str,
        intent: LLMParsedIntent,
        safety: SafetyStatus,
        weather: Optional[Any],
        alerts: List[Any],
        chat_history: List[str],
        trails: List[TrailSummary],
        things_to_do: List[ThingToDo],
        events: List[Event],
        campgrounds: List[Campground],
        visitor_centers: List[VisitorCenter],
        webcams: List[Webcam],
        amenities: List[Amenity],
        photo_spots: List[PhotoSpot] = []
    ) -> LLMResponse: ...

# --- Agent Worker Abstraction ---
class AgentWorker:
    def __init__(self, client: genai.Client, model_name: str, role: str, instruction: str):
        self.client = client
        self.model_name = model_name
        self.role = role
        self.instruction = instruction

    def execute(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.instruction,
                    temperature=0.7 if self.role == "planner" else 0.3
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Agent {self.role} failed: {e}")
            return f"Error generating {self.role} response."

# --- Main Service Implementation ---
class GeminiLLMService:
    def __init__(self, api_key: str, model_name: Optional[str] = None) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required.")
        
        self.model_name = model_name or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
        self.client = genai.Client(api_key=api_key)
        logger.info("Initialized GeminiLLMService (google-genai) with model %s", self.model_name)

        link_instruction = "ALWAYS preserve markdown links [Name](url) from the context in your final output. Do not strip URLs."
        follow_up_instruction = (
            "At the very end of your response, ALWAYS provide 2-3 short, relevant follow-up questions "
            "that the user might want to ask next. Label them 'Suggested Follow-Ups'. "
            "Tailor these to the context (e.g., if talking about hiking, ask about gear or weather)."
        )

        # 1. The Coordinator
        self.agent_coordinator = AgentWorker(
            self.client, self.model_name, "coordinator",
            "You are an intent parser. Extract structured data from queries into JSON."
        )

        # 2. The Planner
        self.agent_planner = AgentWorker(
            self.client, self.model_name, "planner",
            f"You are an expert Travel Planner. Create logical day-by-day itineraries. {link_instruction} {follow_up_instruction}"
        )

        # 3. The Guide
        self.agent_guide = AgentWorker(
            self.client, self.model_name, "guide",
            f"You are a local Park Ranger. Provide ranked lists of options with stats. Speak conversationally. {link_instruction} {follow_up_instruction}"
        )

        # 4. The Safety Officer
        self.agent_safety = AgentWorker(
            self.client, self.model_name, "safety",
            f"You are a Park Safety Officer. Analyze alerts/weather. {link_instruction} {follow_up_instruction}"
        )

        # 5. The Researcher
        self.agent_researcher = AgentWorker(
            self.client, self.model_name, "researcher",
            f"You are a helpful Research Assistant. Display reviews exactly as requested without summarization. {link_instruction} {follow_up_instruction}"
        )

    def parse_user_intent(self, query: str) -> LLMParsedIntent:
        prompt = f"""
        User Query: "{query}"
        
        Analyze query for:
        1. User Prefs
        2. Park Code
        3. Duration
        4. RESPONSE TYPE:
           - "itinerary": "plan trip", "schedule", "X days"
           - "list_options": "best hikes", "list things", "amenities"
           - "safety_info": "is it safe", "weather"
           - "general_chat": "hello", vague, "tell me about park"
           - "reviews": "reviews for X", "what are people saying about X"
           - "entity_lookup": "tell me about [Specific Trail]", "how long is [Trail]"
        5. REVIEW TARGETS: List of explicit trail/place names.
        
        EXAMPLES:
        Query: "Plan a 2 day trip to Zion" -> {{ "response_type": "itinerary", "duration_days": 2, "park_code": "zion" }}
        Query: "Tell me about The Narrows" -> {{ "response_type": "entity_lookup", "review_targets": ["The Narrows"] }}
        Query: "What are people saying about Angels Landing?" -> {{ "response_type": "reviews", "review_targets": ["Angels Landing"] }}
        
        Output strictly valid JSON.
        """
        raw_text = self.agent_coordinator.execute(prompt)
        
        try:
            # Robust JSON extraction
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end != -1:
                json_str = raw_text[start : end + 1]
                data = json.loads(json_str)
                
                # Cleanup
                data.setdefault("raw_query", query)
                if not data.get("duration_days"): data["duration_days"] = 1
                if not data.get("response_type"): data["response_type"] = "general_chat"
                
                # Handle prefs
                if "user_prefs" in data and isinstance(data["user_prefs"], dict):
                    data["user_prefs"] = {k: v for k, v in data["user_prefs"].items() if v is not None}
                    data["user_prefs"] = UserPreference(**data["user_prefs"])
                else:
                    data["user_prefs"] = UserPreference()
                
                return LLMParsedIntent(**data)
        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            return LLMParsedIntent(user_prefs=UserPreference(), raw_query=query, response_type="general_chat")

    def generate_response(
        self,
        *,
        query: str,
        intent: LLMParsedIntent,
        safety: SafetyStatus,
        weather: Optional[Any] = None,
        alerts: List[Any] = None,
        chat_history: List[str],
        trails: List[TrailSummary],
        things_to_do: List[ThingToDo],
        events: List[Event],
        campgrounds: List[Campground],
        visitor_centers: List[VisitorCenter],
        webcams: List[Webcam],
        amenities: List[Amenity],
        photo_spots: List[PhotoSpot] = None
    ) -> LLMResponse:
        alerts = alerts or []
        photo_spots = photo_spots or []
        
        # 1. Handle Entity Lookup (Single Item Detail)
        if intent.response_type == "entity_lookup" and intent.review_targets:
            data_context = self._build_data_context(
                trails, things_to_do, events, campgrounds, visitor_centers, webcams, amenities, safety, weather, alerts,
                photo_spots=photo_spots,
                review_targets=intent.review_targets,
                only_show_targets=True
            )
            prompt = f"""
            ROLE: Park Ranger Guide.
            TASK: The user asked about specific places: {intent.review_targets}.
            INSTRUCTIONS:
            1. Provide a detailed overview of these specific spots (Difficulty, Length, Description).
            2. Mention current weather if relevant to hiking them.
            3. Do NOT list other random trails.
            4. End with follow-up questions.
            
            CONTEXT:
            {data_context}
            
            USER QUERY: '{query}'
            """
            message = self.agent_guide.execute(prompt)

        # 2. Handle Reviews (Deep Dive)
        elif intent.response_type == "reviews" and intent.review_targets:
            data_context = self._build_data_context(
                trails, things_to_do, events, campgrounds, visitor_centers, webcams, amenities, safety, weather, alerts,
                photo_spots=photo_spots,
                review_targets=intent.review_targets,
                only_show_targets=True
            )
            prompt = f"""
            ROLE: Research Assistant.
            TASK: Show reviews for: {intent.review_targets}.
            
            INSTRUCTIONS:
            1. Start with a brief 2-sentence summary of the overall sentiment.
            2. Then list the reviews using the EXACT format below.
            
            STRICT OUTPUT FORMAT PER REVIEW:
            **[Author Name]** | [Date] | [Rating]★
            > "[Review Text]"
            
            [Images on their own line]
            
            3. Do NOT use large headers (###) for the author name. Keep it standard bold.
            4. Do NOT summarize the individual review text; quote it full.
            5. End with follow-up questions.
            
            CONTEXT:
            {data_context}
            
            USER QUERY: '{query}'
            """
            message = self.agent_researcher.execute(prompt)

        # 3. Normal / General Modes
        else:
            data_context = self._build_data_context(
                trails, things_to_do, events, campgrounds, visitor_centers, webcams, amenities, safety, weather, alerts,
                photo_spots=photo_spots
            )
            history_text = "\n".join(chat_history[-5:]) if chat_history else "No previous history."
            
            # Extract park_code for deep-linking
            park_code = intent.park_code or "zion"  # Default fallback
            
            base_prompt = f"""
            PREVIOUS CHAT HISTORY:
            {history_text}
            
            CURRENT CONTEXT:
            {data_context}
            
            USER REQUEST: '{query}'
            """
            
            # Special Handling for Broad Park Overview - only for truly general queries
            # Avoid triggering for specific topics like "events", "trails", "weather", etc.
            query_lower = query.lower()
            specific_topics = ["event", "trail", "hike", "weather", "camping", "campground", 
                               "webcam", "alert", "entrance", "visitor center", "amenities",
                               "photo", "activity", "activities",
                               # Amenity-related terms
                               "gas", "grocery", "store", "restaurant", "food", "lodging", "hotel",
                               "rent", "buy", "gear", "equipment", "supplies", "charging", "medical",
                               "pharmacy", "hospital", "shuttle", "bike", "kayak", "snowshoes"]
            is_specific_query = any(topic in query_lower for topic in specific_topics)
            is_broad_overview = (
                intent.response_type == "general_chat" 
                and not is_specific_query
                and ("tell me about" in query_lower or len(query.split()) < 5)
            )
            
            if is_broad_overview:
                current_month = datetime.now().strftime("%B")
                prompt = f"""
                 ROLE: Expert Park Ranger & Concierge.
                 TASK: Provide a structured park overview for {park_code.upper()}.
                 
                 CONCIERGE GUIDELINES:
                 1. SEASONAL INTELLIGENCE: It is currently {current_month}. Proactively filter or add warnings to trails/activities affected by the 'Alerts' or 'Weather' in context.
                 2. DATA SYNTHESIS: If a road is closed, do NOT recommend trails accessed only by that road without a clear warning.
                 3. TONE: Welcoming, authoritative, and safety-conscious.
                 4. ALERT CROSS-REFERENCING: The TRAILS section already has alerts marked with ⚠️ and clickable links like **[Park Closure](url)**. 
                    When you list a trail that has an alert:
                    - COPY the exact alert markdown from the context (preserve the clickable link!)
                    - DO NOT rewrite or paraphrase - keep the [Category](URL) format intact
                    - If a trail is fully closed, exclude it or offer an alternative
                5. GEAR & HYDRATION: Use the current weather, season, and typical trail difficulty to give practical advice on layers, footwear, sun protection, and water (e.g., “at least 2–3 liters for moderate half‑day hikes”).
                 
                 STRICT OUTPUT FORMAT:
                 
                 ## Welcome to [Park Name]
                 [Brief 2-sentence intro highlighting the park's unique {current_month} character]
                 
                 ### 🌤️ Current Conditions
                 **Status:** [Safety Status from Context]

                 **Weather:** [Weather Summary from Context]

                 **Critical Alerts:** 
                 * [Alert 1 WITH LINK] - *Include a 1-sentence 'Pro-Tip' on how this affects travel.*
                 * [Alert 2 WITH LINK]
                 
                 ### 📍 Park Entrances & Centers
                 [List main Visitor Centers/Entrances WITH LINKS]
                 
                 ### 🥾 Top Experiences (Filtered for {current_month})
                 **Must-Do Trails:**
                 * [Trail Name WITH LINK] ([Difficulty]) - [Brief why-to-go]. ⚠️ **[Alert Category](alert_url)**: [Alert title] (if trail has alert in context)
                 * [Trail 2 Name WITH LINK] ([Difficulty]) - [Brief why-to-go].
                 
                 **Other Highlights:**
                 * [Activity/Photo Spot WITH LINK]
                 
                 ### 📅 Events Today
                 [List Events WITH LINKS or "No specific scheduled events"]

                 ### 🧭 Trail Prep & Safety Tips
                 [2–4 concise bullets covering:]
                 - Recommended clothing layers and footwear for today’s conditions.
                 - Suggested water amount for easy vs. strenuous hikes.
                 - Sun protection (hat, sunscreen, sunglasses) and weather‑specific cautions (ice, mud, heat).
                 - Any special gear to consider (microspikes, trekking poles, rain gear).
                 
                 ---
                 
                 ### 🗺️ Want to explore more?
                 > Use the [**Explore Tab**](#explore) to see the interactive map, weather zones, and service details.
                 > 🥾 Browse the [**Top 10 Trails**](#trails?park={park_code})
                 
                 **Suggested Follow-Ups:**
                 1. "What are the best photo spots for sunrise?"
                 2. "Are there any amenities nearby?"
                 3. "Check current conditions via live webcams."
                 
                 CONTEXT:
                 {data_context}
                 """
                message = self.agent_guide.execute(prompt)

            # if is_broad_overview:
            #      prompt = f"""
            #      ROLE: Park Ranger.
            #      TASK: Provide a structured park overview.
                 
            #      STRICT OUTPUT FORMAT:
                 
            #      ## Welcome to [Park Name]
            #      [Brief 2-sentence intro]
                 
            #      ### 🌤️ Current Conditions
            #      **Status:** [Safety Status from Context]
                 
            #      **Weather:** [Weather Summary from Context]
                 
            #      **Alerts:**
            #      * [Alert 1 WITH LINK]
            #      * [Alert 2 WITH LINK]
                 
            #      ### 📍 Park Entrances & Centers
            #      [List main Visitor Centers/Entrances WITH LINKS]
                 
            #      ### 🥾 Top Experiences
            #      **Must-Do Trails:**
            #      * [Trail 1 Name WITH LINK] ([Difficulty])
            #      * [Trail 2 Name WITH LINK] ([Difficulty])
                 
            #      **Other Highlights:**
            #      * [Activity/Thing To Do 1 WITH LINK]
                 
            #      ### 📅 Events Today
            #      [List Events WITH LINKS or "No specific scheduled events"]
                 
            #      ---
                 
            #      ### Want to explore more? 
                 
            #      > 🗺️ View the interactive map on the [**Explore Tab**](#explore)  
            #      > 🥾 Browse the [**Top 10 Trails**](#trails?park={park_code})
                 
            #      **Suggested Follow-Ups:**
            #      1. "What are the best photo spots?"
            #      2. "Are there any amenities nearby?"
            #      3. "Show me the webcams."
                 
            #      CONTEXT:
            #      {data_context}
                #  """
                 
            
            elif intent.response_type == "itinerary":
                prompt = f"ROLE: Travel Planner. Create {intent.duration_days}-day itinerary.\n{base_prompt}"
                message = self.agent_planner.execute(prompt)
            elif intent.response_type == "safety_info":
                prompt = f"ROLE: Safety Officer. Analyze risks.\n{base_prompt}"
                message = self.agent_safety.execute(prompt)
            # Specific prompts for trail/event/activity queries
            elif any(t in query_lower for t in ["trail", "hike", "hiking"]):
                prompt = f"""
                ROLE: Park Ranger Trail Expert.
                TASK: Show trails from the "TRAILS" section of context data.
                
                CRITICAL INSTRUCTIONS:
                1. LINKS: The context contains `[Trail Name](url)`. COPY THIS EXACTLY for EVERY SINGLE TRAIL. Do not output plain text names.
                2. DO NOT include "ACTIVITIES" or "EVENTS" unless they are hikes.
                2. IMAGES: The context contains `<img ... />`. COPY THIS EXACTLY.
                3. FORMATTING: Put the image on a NEW LINE after the description.
                4. USE THE HTML TAGS PROVIDED.
                5. Group by difficulty.
                
                {base_prompt}
                """
                message = self.agent_guide.execute(prompt)
            elif any(t in query_lower for t in ["event", "events"]):
                 # Rebuild context excluding trails to strictly prevent bleed-over
                context_no_trails = self._build_data_context(
                    trails=[],  # HIDE TRAILS
                    things=things_to_do, events=events, camps=campgrounds, centers=visitor_centers, 
                    cams=webcams, amenities=amenities, safety=safety, weather=weather, alerts=alerts
                )
                
                prompt = f"""
                ROLE: Park Event Coordinator.
                TASK: Show upcoming events from the "EVENTS" section only.
                
                CRITICAL INSTRUCTIONS:
                1. LINKS: Copy `[Event Name](url)` EXACTLY for EVERY event.
                2. IMAGES: Copy the `<img ... />` tag EXACTLY.
                3. USE THE HTML TAGS PROVIDED.
                
                {history_text}
                
                CURRENT CONTEXT:
                {context_no_trails}
                
                USER REQUEST: '{query}'
                """
                message = self.agent_guide.execute(prompt)
            elif any(t in query_lower for t in ["activity", "activities", "things to do"]):
                 # Rebuild context excluding trails AND hiking-related activities
                filtered_things = []
                for thing in things_to_do:
                    activities_lower = [a.get('name', '').lower() for a in thing.activities]
                    tags_lower = [t.lower() for t in thing.tags]
                    is_hiking = any("hike" in a or "hiking" in a for a in activities_lower) or \
                                any("hike" in t or "hiking" in t or "trail" in t for t in tags_lower)
                    
                    # Only include if NOT hiking
                    if not is_hiking:
                        filtered_things.append(thing)

                context_no_trails = self._build_data_context(
                    trails=[],  # HIDE TRAILS
                    things=filtered_things, # FILTERED THINGS
                    events=events, camps=campgrounds, centers=visitor_centers, 
                    cams=webcams, amenities=amenities, safety=safety, weather=weather, alerts=alerts
                )
                
                prompt = f"""
                ROLE: Park Activity Guide.
                TASK: Show independent activities (tours, museums, scenic drives) from the context.
                
                CRITICAL INSTRUCTIONS:
                1. LINKS: Copy `[Activity Name](url)` EXACTLY for EVERY activity.
                2. IMAGES: Copy the `<img ... />` tag EXACTLY.
                3. USE THE HTML TAGS PROVIDED.
                
                {history_text}
                
                CURRENT CONTEXT:
                {context_no_trails}
                
                USER REQUEST: '{query}'
                """
                message = self.agent_guide.execute(prompt)
            elif any(t in query_lower for t in ["photo", "photography", "picture", "shot", "sunrise", "sunset"]):
                # Photo-specific query - use photo spots context
                prompt = f"""
                ROLE: Park Photography Expert.
                TASK: Recommend the best photography spots from the "PHOTO SPOTS" section of context.
                
                CRITICAL INSTRUCTIONS:
                1. Use the PHOTO SPOTS section - these are curated locations for photography.
                2. For each spot, mention: Name (with link if available), Best Time, Tips, and what makes it special.
                3. IMAGES: The context contains `<img ... />`. COPY THIS EXACTLY for each photo spot.
                4. Put the image on a NEW LINE after the description.
                5. Include current weather context for photography conditions.
                6. End with follow-up questions about photography gear or timing.
                
                {base_prompt}
                """
                message = self.agent_guide.execute(prompt)
            elif any(t in query_lower for t in ["restaurant", "food", "eat", "dining", "grocery", "store", 
                                                   "gas", "fuel", "charging", "ev", "medical", "pharmacy", 
                                                   "hospital", "urgent", "clinic", "gear", "rent", "equipment",
                                                   "supplies", "amenity", "amenities", "nearby", "where can"]):
                # Amenity-specific query - prioritize AMENITIES section
                prompt = f"""
                ROLE: Local Services Concierge.
                TASK: Recommend services using the "AMENITIES (Nearby Services)" section of context.
                
                INSTRUCTIONS:
                1. Look in the AMENITIES section for businesses grouped by category.
                2. For EACH business, use this EXACT format with a numbered list:
                
                1. **[Business Name](website_url)** (Type) - ⭐ Rating (review_count reviews)
                   - 📞 Phone | 📍 [Address](maps_url)
                   - *Ranger Note: Brief tip about the vibe or what's good there*
                
                2. **[Next Business](website_url)** (Type) - ⭐ Rating
                   - 📞 Phone | 📍 [Address](maps_url)
                   - *Ranger Note: ...*
                
                3. Each numbered item is ONE business. Use sub-bullets for details.
                4. Business name links to website, address links to Google Maps.
                5. Pick the most relevant businesses for the user's query.
                6. End with a reminder about the Hub Services tab.
                
                {base_prompt}
                """
                message = self.agent_guide.execute(prompt)
            else:
                prompt = f"ROLE: Park Ranger. Be helpful and welcoming.\n{base_prompt}"
                message = self.agent_guide.execute(prompt)
            
            # Add "Explore More" footer for specific topic queries
            if is_specific_query and not is_broad_overview:
                footer = "\n\n---\n\n> **Explore more in Park Explorer:**\n"
                if any(t in query_lower for t in ["trail", "hike", "hiking"]):
                    footer += f"> 🥾 Browse all trails in the [**Trails Browser**](#trails?park={park_code})\n"
                if any(t in query_lower for t in ["event", "events"]):
                    footer += f"> 📅 See all events in the [**Activities & Events**](#activities?park={park_code}) tab\n"
                if any(t in query_lower for t in ["activity", "activities", "things to do"]):
                    footer += f"> 🎯 Browse all activities in the [**Activities & Events**](#activities?park={park_code}) tab\n"
                if any(t in query_lower for t in ["photo", "photos", "photography"]):
                    footer += f"> 📸 See the best [**Photo Spots**](#photos?park={park_code})\n"
                if any(t in query_lower for t in ["webcam", "webcams", "live"]):
                    footer += f"> 📹 View [**Live Webcams**](#webcams?park={park_code})\n"
                # Comprehensive list of amenity/service-related keywords
                amenity_keywords = [
                    # General
                    "amenity", "amenities", "nearby", "where can i", "where to",
                    # Actions
                    "rent", "buy", "purchase", "get", "find", "borrow",
                    # Services
                    "gas", "fuel", "charging", "ev", "atm", "bank", "pharmacy", "medical", 
                    "hospital", "urgent", "clinic", "doctor",
                    # Food & Lodging
                    "restaurant", "food", "eat", "grocery", "store", "shop", "market",
                    "lodging", "hotel", "motel", "cabin", "inn", "campground",
                    # Winter gear
                    "cleats", "spikes", "traction", "snowshoes", "skis", "ski", "snowboard",
                    "poles", "crampons", "ice", "winter gear", "cold weather",
                    # Water activities
                    "kayak", "canoe", "paddle", "paddleboard", "raft", "tube", "boat",
                    # Camping & hiking gear
                    "tent", "sleeping bag", "backpack", "hiking", "boots", "gear", "equipment",
                    "supplies", "flashlight", "lantern", "cooler", "stove",
                    # Transportation
                    "shuttle", "bike", "bicycle", "scooter", "car rental",
                ]
                if any(t in query_lower for t in amenity_keywords):
                    footer += f"> 🏪 See all [**Hub Services**](#essentials?park={park_code}) for nearby amenities\n"
                message += footer

        return LLMResponse(
            message=message,
            safety_status=safety.status,
            safety_reasons=safety.reason,
            suggested_trails=[t.name for t in trails],
            debug_intent=intent
        )

    def _build_data_context(
        self, trails, things, events, camps, centers, cams, amenities, safety, weather, alerts=None,
        photo_spots=None,
        review_targets: Optional[List[str]] = None,
        only_show_targets: bool = False
    ) -> str:
        alerts = alerts or []
        photo_spots = photo_spots or []
        
        # --- Helper: Status Mapper ---
        status_map = {
            "Go": "🟢 Open/Safe",
            "Caution": "🟡 Caution",
            "Danger": "🔴 Danger",
            "Closed": "⚫ Closed"
        }
        safe_status_display = status_map.get(safety.status, safety.status)

        # --- Helper: Weather Formatter ---
        weather_txt = "Weather data unavailable."
        if weather:
            try:
                # Handle both dict (from cache) and Pydantic object
                if isinstance(weather, dict):
                    t = weather.get('current_temp_f', 'N/A')
                    c = weather.get('current_condition', 'N/A')
                    w = weather.get('wind_mph', 'N/A')
                    h = weather.get('humidity', 'N/A')
                    forecast = weather.get('forecast', [])
                    w_alerts = weather.get('weather_alerts', [])
                else:
                    t = getattr(weather, 'current_temp_f', 'N/A')
                    c = getattr(weather, 'current_condition', 'N/A')
                    w = getattr(weather, 'wind_mph', 'N/A')
                    h = getattr(weather, 'humidity', 'N/A')
                    forecast = getattr(weather, 'forecast', [])
                    w_alerts = getattr(weather, 'weather_alerts', [])
                
                weather_txt = f"Currently {t}°F | {c} | Wind: {w}mph | Humidity: {h}%"
                
                # Add 3-day forecast
                if forecast:
                    forecast_lines = []
                    for day in forecast[:3]:
                        if isinstance(day, dict):
                            d_date = day.get('date', '')
                            d_cond = day.get('condition', '')
                            d_high = day.get('maxtemp_f', '')
                            d_low = day.get('mintemp_f', '')
                        else:
                            d_date = getattr(day, 'date', '')
                            d_cond = getattr(day, 'condition', '')
                            d_high = getattr(day, 'maxtemp_f', '')
                            d_low = getattr(day, 'mintemp_f', '')
                        forecast_lines.append(f"{d_date}: {d_cond}, High {d_high}°F / Low {d_low}°F")
                    weather_txt += "\n3-Day Forecast:\n" + "\n".join(forecast_lines)
                
                # Add weather alerts (separate from NPS alerts)
                if w_alerts:
                    weather_txt += "\n⚠️ WEATHER ALERTS:\n"
                    for wa in w_alerts:
                        if isinstance(wa, dict):
                            headline = wa.get('headline', wa.get('event', 'Weather Alert'))
                        else:
                            headline = getattr(wa, 'headline', getattr(wa, 'event', 'Weather Alert'))
                        weather_txt += f"- {headline}\n"
            except Exception as e:
                logger.warning(f"Weather formatting error: {e}")
                weather_txt = str(weather)

        # --- Helper: List Formatter ---
        def link(text, url):
            return f"[{text}]({url})" if url else text

        def fmt(item_list, label, func):
            if not item_list: return f"No {label.lower()}s found."
            lines = []
            for item in item_list[:15]:
                try:
                    lines.append(f"- {func(item)}")
                except Exception:
                    continue
            return "\n".join(lines)

        # --- Trail Formatter (with Images) ---
        # Helper: Check if trail is affected by any alert (same logic as Trail Browser)
        def get_trail_alert(trail_name: str):
            """Check if trail name appears in any alert title/description using phrase matching."""
            if not trail_name or not alerts:
                return None
            
            import re
            trail_lower = trail_name.lower()
            raw_words = trail_lower.split()
            clean_words = [re.sub(r'[^\w-]', '', w) for w in raw_words]
            remove_words = {'trail', 'trails', 'trailhead', 'hike', 'path', 'the', 'and', 'to', 'of', 'at', 'a'}
            words = [w for w in clean_words if w and w not in remove_words]
            
            search_phrases = []
            for i, word in enumerate(words):
                if len(word) > 2:
                    search_phrases.append(word)
                    if i + 1 < len(words):
                        search_phrases.append(f"{word} {words[i+1]}")
            
            if not search_phrases:
                return None
            
            for alert in alerts:
                title = getattr(alert, 'title', '') or ''
                desc = getattr(alert, 'description', '') or ''
                combined = (title + ' ' + desc).lower()
                
                core_name = ' '.join(words)
                alert_url = getattr(alert, 'url', None) or ''
                if core_name and core_name in combined:
                    return {"category": getattr(alert, 'category', 'Closure'), "title": title[:100], "url": alert_url}
                
                for phrase in search_phrases:
                    if ' ' in phrase and phrase in combined:
                        return {"category": getattr(alert, 'category', 'Closure'), "title": title[:100], "url": alert_url}
            
            return None
        
        def format_trail(t):
            is_target = review_targets and any(tgt.lower() in t.name.lower() for tgt in review_targets)
            
            # Get trail URL if available
            trail_url = getattr(t, 'url', None) or getattr(t, 'nps_url', None)
            trail_name_display = link(t.name, trail_url)
            
            # Get first image URL if available
            images = getattr(t, 'images', [])
            image_url = None
            if images and len(images) > 0:
                first_img = images[0]
                image_url = first_img.get('url') if isinstance(first_img, dict) else getattr(first_img, 'url', None)
            
            # Safely access trail attributes with defaults
            difficulty = getattr(t, 'difficulty', None) or 'Unknown'
            length = getattr(t, 'length_miles', None)
            rating = getattr(t, 'average_rating', None)
            
            # Build trail info string
            info_parts = [f"**{trail_name_display}**"]
            if difficulty and difficulty != 'Unknown':
                info_parts.append(f"({difficulty}")
                if length:
                    info_parts[-1] += f", {length}mi)"
                else:
                    info_parts[-1] += ")"
            elif length:
                info_parts.append(f"({length}mi)")
            
            if rating and rating > 0:
                info_parts.append(f"- {rating}★")
            
            base = " ".join(info_parts)
            
            # Check for alerts affecting this trail
            trail_alert = get_trail_alert(t.name)
            if trail_alert:
                # Get park code for fallback URL
                park_code = getattr(t, 'parkCode', None) or 'brca'
                # Use alert URL or fallback to NPS conditions page (like Trail Browser)
                alert_url = trail_alert.get('url') or f"https://www.nps.gov/{park_code.lower()}/planyourvisit/conditions.htm"
                alert_cat = trail_alert['category']
                alert_title = trail_alert['title']
                base += f" ⚠️ **[{alert_cat}]({alert_url})**: {alert_title}"
            
            # Add image on separate line (Resized using HTML with block div)
            if image_url:
                base += f'\n<br><div style="margin-top: 10px;"><img src="{image_url}" width="300" style="border-radius: 5px;" /></div>'
            
            # Handle reviews if present
            recent_reviews = getattr(t, 'recent_reviews', [])
            if recent_reviews:
                if is_target:
                    reviews = []
                    for r in recent_reviews:
                        img_gallery = " &nbsp; ".join([f"![]({u})" for u in r.visible_image_urls])
                        if img_gallery:
                             img_gallery = f"\n{img_gallery}\n"
                        author = r.author if r.author else "Verified Hiker"
                        reviews.append(
                            f"\n---\n"
                            f"**{author}** | {r.date} | {r.rating}★\n"
                            f"> \"{r.text}\"\n"
                            f"{img_gallery}"
                        )
                    return f"{base}\n{''.join(reviews)}"
                else:
                    return f"{base} (Recent reviews available)"
            return base

        # Filter content
        if only_show_targets and review_targets:
            trails = [t for t in trails if any(tgt.lower() in t.name.lower() for tgt in review_targets)]
            things = []
            events = []
            camps = []
            centers = []
            cams = []
            amenities = []

        # Format events with URLs and Images
        def format_event(e):
            event_url = getattr(e, 'url', None)
            
            # Get first image URL if available
            images = getattr(e, 'images', [])
            image_url = None
            if images and len(images) > 0:
                first_img = images[0]
                image_url = first_img.get('url') if isinstance(first_img, dict) else getattr(first_img, 'url', None)
            
            result = f"{link(e.title, event_url)} ({e.date_start})"
            if image_url:
                result += f'\n<br><div style="margin-top: 10px;"><img src="{image_url}" width="300" style="border-radius: 5px;" /></div>'
            return result

        # Format activities with URLs and Images
        def format_activity(a):
            activity_url = getattr(a, 'url', None)
            desc = getattr(a, 'shortDescription', '')[:100]  # Truncate long descriptions
            
            # Get first image URL if available
            images = getattr(a, 'images', [])
            image_url = None
            if images and len(images) > 0:
                first_img = images[0]
                image_url = first_img.get('url') if isinstance(first_img, dict) else getattr(first_img, 'url', None)
            
            result = f"{link(a.title, activity_url)}: {desc}"
            if image_url:
                result += f'\n<br><div style="margin-top: 10px;"><img src="{image_url}" width="300" style="border-radius: 5px;" /></div>'
            return result

        # Format Alerts with URLs and descriptions
        def format_alert(a):
            alert_url = getattr(a, 'url', None)
            title = getattr(a, 'title', 'Alert')
            desc = getattr(a, 'description', '')
            category = getattr(a, 'category', 'Alert')
            title_linked = link(title, alert_url)
            return f"**{category}**: {title_linked}\n  Details: {desc}"
        
        alerts_txt = "\n".join([format_alert(a) for a in alerts]) if alerts else "None"

        return f"""
        === CURRENT CONDITIONS ===
        STATUS: {safe_status_display}
        WEATHER: {weather_txt}
        ALERTS: {alerts_txt}

        === PARK DATA ===
        TRAILS:
        {fmt(trails, "Trail", format_trail)}

        CAMPGROUNDS:
        {fmt(camps, "Campground", lambda x: f"{link(x.name, getattr(x, 'url', None))} (Status: {x.isOpen})")}

        VISITOR CENTERS:
        {fmt(centers, "Center", lambda x: link(x.name, getattr(x, 'url', None)))}
        
        ACTIVITIES:
        {fmt(things, "Activity", format_activity)}
        
        EVENTS:
        {fmt(events, "Event", format_event)}
        
        PHOTO SPOTS:
        {self._format_photo_spots(photo_spots)}
        
        AMENITIES (Nearby Services):
        {self._format_amenities(amenities)}
        """
    
    def _format_photo_spots(self, photo_spots) -> str:
        """Format photo spots for LLM context with images."""
        if not photo_spots:
            return "No photo spots available."
        
        lines = []
        for ps in photo_spots[:10]:  # Limit to 10
            try:
                # Handle both Pydantic model and dict
                if hasattr(ps, 'name'):
                    name = ps.name
                    best_time = getattr(ps, 'best_time_of_day', [])
                    tips = getattr(ps, 'tips', [])
                    description = getattr(ps, 'description', '')
                    image_url = getattr(ps, 'image_url', None)
                    source_url = getattr(ps, 'source_url', None)
                    rank = getattr(ps, 'rank', None)
                else:
                    name = ps.get('name', 'Unknown')
                    best_time = ps.get('best_time_of_day', [])
                    tips = ps.get('tips', [])
                    description = ps.get('description', '')
                    image_url = ps.get('image_url', None)
                    source_url = ps.get('source_url', None)
                    rank = ps.get('rank', None)
                
                # Format best time as string
                best_time_str = ", ".join(best_time) if isinstance(best_time, list) else str(best_time) if best_time else ""
                
                # Build name with optional link and rank
                if source_url:
                    name_display = f"[{name}]({source_url})"
                else:
                    name_display = name
                
                line = f"- **{name_display}**"
                if rank:
                    line += f" (Rank #{rank})"
                if best_time_str:
                    line += f" | Best time: {best_time_str}"
                if description:
                    line += f"\n  {description[:200]}"
                if tips and len(tips) > 0:
                    first_tip = tips[0] if isinstance(tips, list) else str(tips)
                    line += f"\n  *Tip: {first_tip[:100]}*"
                
                # Add image (like trails)
                if image_url:
                    line += f'\n<br><div style="margin-top: 10px;"><img src="{image_url}" width="300" style="border-radius: 5px;" /></div>'
                
                lines.append(line)
            except Exception:
                continue
        
        return "\n".join(lines) if lines else "No photo spots available."
    
    def _format_amenities(self, amenities) -> str:
        """Format amenities for LLM context, grouped by category."""
        if not amenities:
            return "No nearby amenities available."
        
        # Group amenities by type for easier LLM parsing
        # Food-related types
        food_types = {'restaurant', 'cafe', 'brewpub', 'american restaurant', 'mexican restaurant',
                      'pizza', 'bakery', 'coffee', 'diner', 'bistro', 'grill', 'southwestern restaurant (us)'}
        gas_types = {'gas station', 'fuel', 'gas', 'convenience store'}
        medical_types = {'hospital', 'urgent care', 'pharmacy', 'medical', 'emergency room', 'clinic'}
        
        grouped = {"🍽️ RESTAURANTS & FOOD": [], "⛽ GAS & FUEL": [], "🏥 MEDICAL": [], "🏪 OTHER SERVICES": []}
        
        for a in amenities:
            try:
                # Handle both Pydantic model and dict
                if hasattr(a, 'name'):
                    name = a.name
                    address = getattr(a, 'address', '')
                    lat = getattr(a, 'latitude', None)
                    lon = getattr(a, 'longitude', None)
                    website = getattr(a, 'website', None)
                    phone = getattr(a, 'phone', None)
                    distance = getattr(a, 'distance_miles', None)
                    amenity_type = getattr(a, 'type', '')
                    rating = getattr(a, 'rating', None)
                    rating_count = getattr(a, 'rating_count', None)
                else:
                    name = a.get('name', 'Unknown')
                    address = a.get('address', '')
                    lat = a.get('latitude', None)
                    lon = a.get('longitude', None)
                    website = a.get('website', None)
                    phone = a.get('phone', None)
                    distance = a.get('distance_miles', None)
                    amenity_type = a.get('type', '')
                    rating = a.get('rating', None)
                    rating_count = a.get('rating_count', None)
                
                # Build Google Maps URL
                if lat and lon:
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                elif address:
                    safe_addr = address.replace(' ', '+').replace(',', '%2C')
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={safe_addr}"
                else:
                    maps_url = None
                
                # Build formatted line - name links to website, address links to maps
                if website:
                    name_display = f"[{name}]({website})"
                else:
                    name_display = f"**{name}**"
                
                if maps_url and address:
                    address_display = f"[{address}]({maps_url})"
                elif address:
                    address_display = address
                else:
                    address_display = None
                
                line = f"- **{name_display}** ({amenity_type})"
                if distance:
                    line += f" - {distance:.1f} mi"
                if rating and rating_count:
                    line += f" | ⭐ {rating} ({rating_count} reviews)"
                if phone:
                    line += f" | 📞 {phone}"
                if address_display:
                    line += f" | 📍 {address_display}"
                
                # Categorize
                type_lower = amenity_type.lower() if amenity_type else ''
                if any(ft in type_lower for ft in food_types):
                    grouped["🍽️ RESTAURANTS & FOOD"].append(line)
                elif any(gt in type_lower for gt in gas_types):
                    grouped["⛽ GAS & FUEL"].append(line)
                elif any(mt in type_lower for mt in medical_types):
                    grouped["🏥 MEDICAL"].append(line)
                else:
                    grouped["🏪 OTHER SERVICES"].append(line)
                    
            except Exception:
                continue
        
        # Build output with category headers
        output = []
        for category, items in grouped.items():
            if items:
                output.append(f"\n{category}:")
                output.extend(items[:8])  # Limit 8 per category
        
        return "\n".join(output) if output else "No nearby amenities available."

    def extract_reviews_from_text(self, text: str) -> List[TrailReview]:
        truncated_text = text[:60000] 
        prompt = f"""
        TASK: Extract the most recent 10 reviews.
        OUTPUT JSON: {{ "reviews": [ {{ "author": "...", "rating": 5, "date": "...", "text": "...", "visible_image_urls": [] }} ] }}
        CONTENT: {truncated_text}
        """
        raw = self.agent_researcher.execute(prompt)
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1:
                data = json.loads(raw[start:end+1])
                return [TrailReview(**r) for r in data.get("reviews", [])]
        except Exception:
            return []
        return []
