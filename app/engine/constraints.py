import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.models import TrailSummary, WeatherSummary, Alert

logger = logging.getLogger(__name__)

class UserPreference(BaseModel):
    max_difficulty: str = "hard"
    min_rating: float = 3.5
    max_length_miles: float = 20.0
    dog_friendly: bool = False
    kid_friendly: bool = False
    wheelchair_accessible: bool = False

class SafetyStatus(BaseModel):
    status: str
    reason: List[str] = []

class ConstraintEngine:
    def __init__(self):
        pass

    def filter_trails(self, trails: List[TrailSummary], prefs: UserPreference) -> List[TrailSummary]:
        filtered = []
        
        # Difficulty Mapping: easy=1, moderate=2, hard=3
        difficulty_rank = {"easy": 1, "moderate": 2, "hard": 3}
        user_diff_rank = difficulty_rank.get(prefs.max_difficulty.lower(), 3)

        for trail in trails:
            # 1. Difficulty Check
            trail_diff_rank = difficulty_rank.get(trail.difficulty.lower(), 3)
            if trail_diff_rank > user_diff_rank:
                continue

            # 2. Length Check
            if trail.length_miles > prefs.max_length_miles:
                continue

            # 3. Rating Check
            if trail.average_rating < prefs.min_rating:
                continue

            # 4. Feature Checks
            features_lower = [f.lower() for f in trail.features]
            
            if prefs.dog_friendly:
                # A. Explicit Reject
                if any("no dog" in f for f in features_lower):
                    continue
                
                # B. Explicit Accept (must contain 'dog' and NOT be the 'no dog' tag)
                # Since we already filtered 'no dog' tags in step A? 
                # No, step A skips the TRAIL if it has 'no dog'. 
                # But a trail might have NO dog tags at all. We should skip those too? 
                # Yes, strict mode: only show trails KNOWN to be dog friendly.
                
                is_friendly = False
                for f in features_lower:
                    if "dog" in f and "no dog" not in f:
                        is_friendly = True
                        break
                
                if not is_friendly:
                    continue
            
            if prefs.kid_friendly:
                if not any("kid" in f for f in features_lower):
                    continue
                    
            if prefs.wheelchair_accessible:
                if not any("wheelchair" in f or "ada" in f for f in features_lower):
                    continue

            filtered.append(trail)
        
        return filtered


    def analyze_safety(self, weather: Optional[WeatherSummary], alerts: List[Alert]) -> SafetyStatus:
        reasons = []
        status = "Go"

        # --- 1. Weather Checks ---
        if weather:
            if weather.current_temp_f > 110:
                status = "No-Go"
                reasons.append(f"Extreme heat detected: {weather.current_temp_f}°F.")
            elif weather.current_temp_f < 10:
                status = "No-Go"
                reasons.append(f"Extreme cold detected: {weather.current_temp_f}°F.")
            
            for day in weather.forecast[:3]:
                cond = day.condition.lower()
                if "snow" in cond or "blizzard" in cond:
                    if status != "No-Go": status = "Caution"
                    reasons.append(f"Snow forecast for {day.date}.")
                
                if "storm" in cond or "thunder" in cond:
                    if status != "No-Go": status = "Caution"
                    reasons.append(f"Storms forecast for {day.date}.")

        # --- 2. Alert Checks ---
        for alert in alerts:
            title_lower = alert.title.lower()
            if "closure" in title_lower or "danger" in title_lower or "closed" in title_lower:
                if "park" in title_lower and "closed" in title_lower:
                    status = "No-Go"
                    reasons.append(f"Critical Alert: {alert.title}")
                else:
                    if status != "No-Go": status = "Caution"
                    reasons.append(f"Safety Alert: {alert.title}")

        return SafetyStatus(status=status, reason=reasons)
