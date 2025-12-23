from __future__ import annotations

import json
import logging
from typing import List, Optional, Protocol

import google.generativeai as genai
from pydantic import BaseModel, Field, ValidationError

from app.engine.constraints import UserPreference, SafetyStatus
from app.models import TrailSummary, ThingToDo, Event

logger = logging.getLogger(__name__)


class LLMParsedIntent(BaseModel):
    user_prefs: UserPreference
    park_code: Optional[str] = None
    target_date: Optional[str] = None
    duration_days: int = 1
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
        events: List[Event]
    ) -> LLMResponse: ...


class GeminiLLMService:
    def __init__(self, api_key: str, model_name: str = "gemini-3-flash-preview") -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for GeminiLLMService")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        logger.info("Initialized GeminiLLMService with model %s", model_name)

    def parse_user_intent(self, query: str) -> LLMParsedIntent:
        prompt = f"""
You are an intent parser for an outdoor adventure concierge.

User query: \"{query}\".

Extract user preferences into a strictly valid JSON object.
Return ONLY JSON. Do not wrap the output in markdown.

JSON Schema:
{{
  "user_prefs": {{
    "max_difficulty": "easy" | "moderate" | "hard",
    "min_rating": float,
    "max_length_miles": float,
    "dog_friendly": bool,
    "kid_friendly": bool,
    "wheelchair_accessible": bool
  }},
  "park_code": "yose" | "zion" | "grca" | null,
  "target_date": string | null,
  "duration_days": integer (default 1),
  "raw_query": string
}}
"""
        response = self.model.generate_content(prompt)
        text = response.text.strip()

        # Robust JSON extraction
        try:
            start_idx = text.find("{")
            end_idx = text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                text = text[start_idx : end_idx + 1]

            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Failed to decode Gemini JSON: %s | text=%r", e, text)
            raise

        try:
            data.setdefault("raw_query", query)
            if "duration_days" not in data or not data["duration_days"]:
                data["duration_days"] = 1
                
            if "user_prefs" in data and isinstance(data["user_prefs"], dict):
                data["user_prefs"] = {
                    k: v for k, v in data["user_prefs"].items() 
                    if v is not None
                }
                data["user_prefs"] = UserPreference(**data["user_prefs"])
            else:
                data["user_prefs"] = UserPreference()
                
            intent = LLMParsedIntent(**data)
        except ValidationError as e:
            logger.error("Validation error: %s | data=%r", e, data)
            raise

        return intent

    def generate_response(
        self,
        *,
        query: str,
        intent: LLMParsedIntent,
        safety: SafetyStatus,
        trails: List[TrailSummary],
        things_to_do: List[ThingToDo],
        events: List[Event]
    ) -> LLMResponse:
        """
        Generates a natural language itinerary using the LLM.
        """
        # Limit context size
        context_trails = [
            f"- Trail: {t.name} ({t.difficulty}, {t.length_miles}mi)" 
            for t in trails[:10]
        ]
        context_things = [
            f"- Activity: {t.title}: {t.shortDescription}" 
            for t in things_to_do[:10]
        ]
        context_events = [
            f"- Event: {e.title} ({e.date_start})" 
            for e in events[:5]
        ]

        safety_msg = f"Status: {safety.status}"
        if safety.reason:
            safety_msg += f"\nAlerts: {', '.join(safety.reason)}"

        prompt = f"""
You are an expert National Park Guide.
User Request: "{query}"
Trip Duration: {intent.duration_days} day(s).
Safety Status: {safety_msg}

Available Options (already filtered):
{chr(10).join(context_trails) if context_trails else "No specific trails."}

{chr(10).join(context_things) if context_things else "No specific activities."}

{chr(10).join(context_events) if context_events else "No events."}

TASK:
Create a suggested {intent.duration_days}-day itinerary.
- Use the provided options to fill the days.
- Include specific trails and activities.
- If Safety is NOT "Go", mention warnings prominently.
- Format clearly with Markdown.
"""
        
        response = self.model.generate_content(prompt)
        message = response.text.strip()
        
        return LLMResponse(
            message=message,
            safety_status=safety.status,
            safety_reasons=safety.reason,
            suggested_trails=[t.name for t in trails],
            debug_intent=intent
        )
