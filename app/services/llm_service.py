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
from app.clients.external_client import ExternalClient


logger = logging.getLogger(__name__)

# --- Response Types ---
ResponseType = Literal["itinerary", "list_options", "safety_info", "general_chat", "reviews"]


# --- DTOs ---
class LLMParsedIntent(BaseModel):
    user_prefs: UserPreference
    park_code: Optional[str] = None
    target_date: Optional[str] = None
    duration_days: int = 1
    response_type: ResponseType = "itinerary"
    review_targets: List[str] = Field(default_factory=list) # Names of trails to fetch reviews for
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
        
        # Use env var if provided, otherwise fallback to stable flash
        self.model_name = model_name or os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
        self.client = genai.Client(api_key=api_key)
        
        logger.info("Initialized GeminiLLMService (google-genai) with model %s", self.model_name)

        # Common instruction fragment to force link preservation
        link_instruction = "ALWAYS preserve markdown links [Name](url) from the context in your final output. Do not strip URLs."

        # 1. The Coordinator
        self.agent_coordinator = AgentWorker(
            self.client, self.model_name, "coordinator",
            "You are an intent parser. Extract structured data from queries into JSON."
        )

        # 2. The Planner
        self.agent_planner = AgentWorker(
            self.client, self.model_name, "planner",
            f"You are an expert Travel Planner. Create logical day-by-day itineraries. {link_instruction}"
        )

        # 3. The Guide
        self.agent_guide = AgentWorker(
            self.client, self.model_name, "guide",
            f"You are a local Park Ranger. Provide ranked lists of options with stats. {link_instruction}"
        )

        # 4. The Safety Officer
        self.agent_safety = AgentWorker(
            self.client, self.model_name, "safety",
            f"You are a Park Safety Officer. Analyze alerts/weather. {link_instruction}"
        )

        # 5. The Researcher (Extraction Specialist)
        self.agent_researcher = AgentWorker(
            self.client, self.model_name, "researcher",
            "You are a Data Researcher. Extract structured data from raw content. Focus on reviews, ratings, dates, and specifically IMAGE URLs associated with reviews."
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
   - "general_chat": "hello", vague
   - "reviews": "reviews for X", "what are people saying about X"

5. REVIEW TARGETS: List of explicit trail/place names the user wants reviews for.

EXAMPLES:
Query: "Plan a 2 day trip to Zion"
Result: {{ "response_type": "itinerary", "duration_days": 2, "park_code": "zion" }}

Query: "Best hikes in Yosemite"
Result: {{ "response_type": "list_options", "park_code": "yose" }}

Query: "What do people say about Angels Landing and The Narrows?"
Result: {{ "response_type": "reviews", "review_targets": ["Angels Landing", "The Narrows"] }}

Query: "Latest reviews for Kayenta Trail"
Result: {{ "response_type": "reviews", "review_targets": ["Kayenta Trail"] }}

Output strictly valid JSON:
{{
  "user_prefs": {{ ... }},
  "park_code": "...",
  "target_date": "...",
  "duration_days": 1,
  "response_type": "itinerary" | "list_options" | "safety_info" | "general_chat" | "reviews",
  "review_targets": ["Angel's Landing", "Narrows"],
  "raw_query": "..."
}}
"""
        raw_text = self.agent_coordinator.execute(prompt)
        text = raw_text

        # 1. Clean Markdown Fences (Robustly)
        # We assume the model might wrap response in ```json ... ```
        # We strip strictly based on content finding, avoiding fragile string literals.
        try:
            # Locate JSON boundaries
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                text = text[start : end + 1]
            
            data = json.loads(text)
            
            # Defaults & Cleanup
            data.setdefault("raw_query", query)
            if not data.get("duration_days"): data["duration_days"] = 1
            if not data.get("response_type"): data["response_type"] = "itinerary"
            
            if "user_prefs" in data and isinstance(data["user_prefs"], dict):
                # Scrub None values to let Pydantic defaults work
                data["user_prefs"] = {k: v for k, v in data["user_prefs"].items() if v is not None}
                data["user_prefs"] = UserPreference(**data["user_prefs"])
            else:
                data["user_prefs"] = UserPreference()

            return LLMParsedIntent(**data)

        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Intent parsing failed: {e} | Text: {text}")
            # Fallback intent so the app doesn't crash
            return LLMParsedIntent(user_prefs=UserPreference(), raw_query=query, response_type="general_chat")


    def generate_response(
        self,
        *,
        query: str,
        intent: LLMParsedIntent,
        safety: SafetyStatus,
        trails: List[TrailSummary],
        things_to_do: List[ThingToDo],
        events: List[Event],
        campgrounds: List[Campground],
        visitor_centers: List[VisitorCenter],
        webcams: List[Webcam],
        amenities: List[Amenity]
    ) -> LLMResponse:
        
        data_context = self._build_data_context(
            trails, things_to_do, events, campgrounds, visitor_centers, webcams, amenities, safety
        )
        
        if intent.response_type == "itinerary":
            prompt = f"REQUEST: Plan {intent.duration_days}-day itinerary for '{query}'.\nCONTEXT:\n{data_context}"
            message = self.agent_planner.execute(prompt)

        elif intent.response_type == "list_options":
            prompt = f"REQUEST: List recommendations for '{query}'.\nCONTEXT:\n{data_context}"
            message = self.agent_guide.execute(prompt)

        elif intent.response_type == "safety_info":
            prompt = f"REQUEST: Safety check for '{query}'.\nCONTEXT:\n{data_context}"
            message = self.agent_safety.execute(prompt)
            
        else:
            prompt = f"REQUEST: Respond to '{query}'.\nCONTEXT:\n{data_context}"
            message = self.agent_guide.execute(prompt)

        return LLMResponse(
            message=message,
            safety_status=safety.status,
            safety_reasons=safety.reason,
            suggested_trails=[t.name for t in trails],
            debug_intent=intent
        )

    def extract_reviews_from_text(self, text: str) -> List[TrailReview]:
        """
        Uses the Researcher agent to parse raw text/markdown into structured TrailReview objects.
        """
        # Truncate if too huge to avoid context limits, but keep enough for recent reviews
        truncated_text = text[:60000] 
        
        prompt = f"""
        TASK: Extract the most recent 10 reviews from this content.
        
        OUTPUT JSON:
        {{
            "reviews": [
                {{
                    "author": "Name",
                    "rating": 5,
                    "date": "YYYY-MM-DD" (or raw string if relative),
                    "text": "Full review text...",
                    "condition_tags": ["tag1", "tag2"],
                    "visible_image_urls": ["url1", "url2"]
                }}
            ]
        }}
        
        CONTENT:
        {truncated_text}
        """
        
        raw_response = self.agent_researcher.execute(prompt)
        
        try:
            # Clean generic markdown fences
            clean_text = raw_response
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1:
                clean_text = clean_text[start : end + 1]
            
            data = json.loads(clean_text)
            reviews_data = data.get("reviews", [])
            
            results = []
            for r in reviews_data:
                try:
                    # Basic validation/cleaning
                    if not r.get('author'): r['author'] = "Anonymous"
                    if not r.get('text'): r['text'] = ""
                    if not r.get('rating'): r['rating'] = 0
                    
                    results.append(TrailReview(**r))
                except Exception as e:
                    logger.warning(f"Skipping malformed review: {e}")
                    continue
            
            return results

        except Exception as e:
            logger.error(f"Failed to extract reviews with Researcher agent: {e}")
            return []

    def _build_data_context(self, trails, things, events, camps, centers, cams, amenities, safety) -> str:
        # Helper to make a link if url exists (safely checking attributes)
        def link(text, url):
            if url:
                return f"[{text}]({url})"
            return text

        # Robust formatter
        def fmt(item_list, label, func):
            # Explicitly check for None or empty
            if not item_list: 
                return f"NO {label} FOUND."
            
            # Use 'item_list' consistently
            lines = []
            for item in item_list[:15]: # Increased limit to 15
                try:
                    lines.append(f"- [{label}] {func(item)}")
                except Exception:
                    continue # Skip malformed items
            return "\n".join(lines)

        # 1. Trails (Reviews + Rating)
        def format_trail(t):
           base = f"{t.name} ({t.difficulty}, {t.length_miles}mi) {t.average_rating}★"
           if t.recent_reviews:
               # Add summary of last 3 reviews to context
               reviews_summary = " ".join([f"[{r.date}: {r.text[:100]}...]" for r in t.recent_reviews[:3]])
               # Add images from reviews
               images = []
               for r in t.recent_reviews:
                   images.extend(r.visible_image_urls)
               
               # Limit images to avoid context bloat
               img_md = " ".join([f"![]({url})" for url in images[:3]])
               return f"{base}\n    Recent Reviews: {reviews_summary}\n    Images: {img_md}"
           return base

        t_txt = fmt(trails, "Trail", format_trail)

        # 2. Activities (With URLs)
        # Check if 'url' attr exists, otherwise fallback
        a_txt = fmt(things, "Activity", lambda x: f"{link(x.title, getattr(x, 'url', None))}: {x.shortDescription}")

        # 3. Events
        e_txt = fmt(events, "Event", lambda x: f"{x.title} ({x.date_start})")

        # 4. Campgrounds (With Reservation URL)
        c_txt = fmt(camps, "Campground", lambda x: f"{link(x.name, getattr(x, 'reservationUrl', None) or getattr(x, 'url', None))} (Open: {x.isOpen})")

        # 5. Visitor Centers
        v_txt = fmt(centers, "Visitor Center", lambda x: f"{link(x.name, getattr(x, 'url', None))}")

        # 6. Webcams
        w_txt = fmt(cams, "Webcam", lambda x: f"{link(x.title, getattr(x, 'url', None))} ({x.status})")

        # 7. Amenities (Serper Maps URL)
        am_txt = fmt(amenities, "Amenity", lambda x: f"{link(x.name, getattr(x, 'google_maps_url', None))} ({x.type})")

        return f"""
SAFETY STATUS: {safety.status}
ALERTS: {', '.join(safety.reason)}

AVAILABLE TRAILS:
{t_txt}

ACTIVITIES:
{a_txt}

EVENTS:
{e_txt}

CAMPGROUNDS:
{c_txt}

VISITOR CENTERS:
{v_txt}

AMENITIES (Nearby):
{am_txt}

WEBCAMS:
{w_txt}
"""
