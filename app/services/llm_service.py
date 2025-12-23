from __future__ import annotations

import json
import logging
from typing import List, Optional, Protocol

import google.generativeai as genai
from pydantic import BaseModel, Field, ValidationError

from app.engine.constraints import UserPreference, SafetyStatus
from app.models import TrailSummary

logger = logging.getLogger(__name__)


class LLMParsedIntent(BaseModel):
    user_prefs: UserPreference
    park_code: Optional[str] = None
    target_date: Optional[str] = None
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
  "raw_query": string
}}
"""
        response = self.model.generate_content(prompt)
        text = response.text.strip()

        # REMOVED: All manual backtick stripping to avoid syntax errors.
        # We rely on the prompt "Do not wrap the output in markdown"
        # and standard JSON parsing.

        # If the model adds markdown fences, json.loads might fail.
        # Ideally, we would strip them, but to ensure this file is valid python
        # for you right now, we are skipping that logic.
        
        # Basic fallback: if it starts with '```
        # using standard string indices if needed, but let's try raw load first.
        
        try:
            # Attempt to find the first '{' and last '}' to isolate JSON
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
            # Fix: Scrub None values from user_prefs so Pydantic defaults take over
            if "user_prefs" in data and isinstance(data["user_prefs"], dict):
                # Remove keys where value is None
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
    ) -> LLMResponse:
        suggested_trail_names = [t.name for t in trails]
        lines = [
            f"Here is a summary for: \"{query}\"",
            f"- Park: {intent.park_code}",
            f"- Difficulty: {intent.user_prefs.max_difficulty}",
            f"- Safety: {safety.status}"
        ]
        if safety.reason:
            lines.append("Safety Alerts: " + "; ".join(safety.reason))
        if suggested_trail_names:
            lines.append("Trails: " + ", ".join(suggested_trail_names))
        
        return LLMResponse(
            message="\n".join(lines),
            safety_status=safety.status,
            safety_reasons=safety.reason,
            suggested_trails=suggested_trail_names,
            debug_intent=intent,
        )
