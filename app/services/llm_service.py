from __future__ import annotations

import json
import logging
import os
from typing import List, Optional, Protocol, Literal, Any

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from app.engine.constraints import UserPreference, SafetyStatus
from app.models import TrailSummary, ThingToDo, Event, Campground, VisitorCenter, Webcam, Amenity, TrailReview

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
        chat_history: List[str],
        trails: List[TrailSummary],
        things_to_do: List[ThingToDo],
        events: List[Event],
        campgrounds: List[Campground],
        visitor_centers: List[VisitorCenter],
        webcams: List[Webcam],
        amenities: List[Amenity]
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
        
        self.model_name = model_name or os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
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
        chat_history: List[str],
        trails: List[TrailSummary],
        things_to_do: List[ThingToDo],
        events: List[Event],
        campgrounds: List[Campground],
        visitor_centers: List[VisitorCenter],
        webcams: List[Webcam],
        amenities: List[Amenity]
    ) -> LLMResponse:
        
        # 1. Handle Entity Lookup (Single Item Detail)
        if intent.response_type == "entity_lookup" and intent.review_targets:
            data_context = self._build_data_context(
                trails, things_to_do, events, campgrounds, visitor_centers, webcams, amenities, safety, weather,
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
                trails, things_to_do, events, campgrounds, visitor_centers, webcams, amenities, safety, weather,
                review_targets=intent.review_targets,
                only_show_targets=True
            )
            prompt = f"""
            ROLE: Research Assistant.
            TASK: Show reviews for: {intent.review_targets}.
            
            INSTRUCTIONS:
            1. Start with a brief 2-sentence summary of the overall sentiment (e.g. "Hikers report muddy conditions but great views...").
            2. Then list the reviews using the EXACT format below.
            
            STRICT OUTPUT FORMAT PER REVIEW:
            **[Author Name]** | [Date] | [Rating]★
            > "[Review Text]"
            
            [Images on their own line]
            
            3. Do NOT use large headers (###) for the author name. Keep it standard bold.
            4. Do NOT summarize the individual review text; quote it full.
            5. Copy the structure above exactly.
            6. End with follow-up questions.
            
            CONTEXT:
            {data_context}
            
            USER QUERY: '{query}'
            """
            message = self.agent_researcher.execute(prompt)

        # 3. Normal / General Modes
        else:
            data_context = self._build_data_context(
                trails, things_to_do, events, campgrounds, visitor_centers, webcams, amenities, safety, weather
            )
            history_text = "\n".join(chat_history[-5:]) if chat_history else "No previous history."
            
            base_prompt = f"""
            PREVIOUS CHAT HISTORY:
            {history_text}
            
            CURRENT CONTEXT:
            {data_context}
            
            USER REQUEST: '{query}'
            """
            
            if intent.response_type == "itinerary":
                prompt = f"ROLE: Travel Planner. Create {intent.duration_days}-day itinerary.\n{base_prompt}"
                message = self.agent_planner.execute(prompt)
            elif intent.response_type == "safety_info":
                prompt = f"ROLE: Safety Officer. Analyze risks.\n{base_prompt}"
                message = self.agent_safety.execute(prompt)
            else:
                prompt = f"ROLE: Park Ranger. Be helpful and welcoming.\n{base_prompt}"
                message = self.agent_guide.execute(prompt)

        return LLMResponse(
            message=message,
            safety_status=safety.status,
            safety_reasons=safety.reason,
            suggested_trails=[t.name for t in trails],
            debug_intent=intent
        )

    def _build_data_context(
        self, trails, things, events, camps, centers, cams, amenities, safety, weather,
        review_targets: Optional[List[str]] = None,
        only_show_targets: bool = False
    ) -> str:
        
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
                # Direct attribute access (Pydantic)
                t = getattr(weather, 'current_temp_f', 'N/A')
                c = getattr(weather, 'current_condition', 'N/A')
                w = getattr(weather, 'wind_mph', 'N/A')
                weather_txt = f"{t}°F | {c} | Wind: {w}mph"
            except Exception:
                weather_txt = str(weather)

        # --- Helper: List Formatter ---
        def link(text, url):
            return f"[{text}]({url})" if url else text

        def fmt(item_list, label, func):
            if not item_list: return f"NO {label} FOUND."
            lines = []
            for item in item_list[:15]:
                try:
                    lines.append(f"- [{label}] {func(item)}")
                except Exception:
                    continue
            return "\n".join(lines)

        # --- Trail Formatter (Strict Layout) ---
        def format_trail(t):
            is_target = review_targets and any(tgt.lower() in t.name.lower() for tgt in review_targets)
            
            base = f"**{t.name}** ({t.difficulty}, {t.length_miles}mi) - {t.average_rating}★"
            
            if t.recent_reviews:
                if is_target:
                    # Detailed Review View
                    reviews = []
                    for r in t.recent_reviews:
                        # 1. Image Gallery (Separated by non-breaking spaces)
                        img_gallery = " &nbsp; ".join([f"![]({u})" for u in r.visible_image_urls])
                        if img_gallery:
                             img_gallery = f"\n{img_gallery}\n"
                        
                        # 2. Author/Date Logic
                        author = r.author if r.author else "Verified Hiker"
                        
                        # 3. Output Block (No H3 headers, just bold)
                        reviews.append(
                            f"\n---\n"
                            f"**{author}** | {r.date} | {r.rating}★\n"
                            f"> \"{r.text}\"\n"
                            f"{img_gallery}"
                        )
                    return f"{base}\n{''.join(reviews)}"
                else:
                    # Summary View
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

        return f"""
        === CURRENT CONDITIONS ===
        STATUS: {safe_status_display}
        WEATHER: {weather_txt}
        ALERTS: {', '.join(safety.reason)}

        === PARK DATA ===
        TRAILS:
        {fmt(trails, "Trail", format_trail)}

        CAMPGROUNDS:
        {fmt(camps, "Campground", lambda x: f"{link(x.name, getattr(x, 'url', None))} (Status: {x.isOpen})")}

        VISITOR CENTERS:
        {fmt(centers, "Center", lambda x: link(x.name, getattr(x, 'url', None)))}
        
        ACTIVITIES:
        {fmt(things, "Activity", lambda x: x.title)}
        """

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
