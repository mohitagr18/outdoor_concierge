# Outdoor Concierge - LLM & Caching Enhancements

**Date:** 2026-01-06  
**Summary:** Enhanced the LLM service to provide complete trail data with URLs, implemented persistent daily caching for dynamic data, and fixed multiple bugs in the weather/alerts passthrough.

---

## 1. Trail URL Support

### Problem
When asking "Tell me about Zion," trails listed in the response didn't have clickable URLs.

### Solution
**File: `app/models.py`**
- Added `nps_url: Optional[str]` and `alltrails_url: Optional[str]` fields to `TrailSummary`
- Added computed `@property url` that returns `nps_url` if available, else `alltrails_url`

```python
@property
def url(self) -> Optional[str]:
    return self.nps_url if self.nps_url else self.alltrails_url
```

The existing `format_trail` function in `llm_service.py` already had `getattr(t, 'url', None)`, so this automatically worked.

---

## 2. Trail Filtering Relaxation

### Problem
For general queries like "Tell me about Zion," trails with low ratings (< 3.5) were being filtered out, preventing the LLM from seeing all available data.

### Solution
**File: `app/orchestrator.py`**
- Added relaxation logic in `handle_query`:
  - For `general_chat`, `entity_lookup`, or `reviews` intents
  - If no explicit user preferences are set
  - Use `raw_trails` (all trails) instead of `vetted_trails` (filtered)

```python
if intent.response_type in ["general_chat", "entity_lookup", "reviews"]:
    if not intent.user_prefs or intent.user_prefs == UserPreference():
        vetted_trails = raw_trails
```

---

## 3. Persistent Daily Caching

### Problem
Weather, alerts, and events were fetched on every request, wasting API calls. User wanted data cached per day across sessions.

### Solution

**File: `app/services/data_manager.py`**
Added 3 new methods:
- `_get_daily_cache_path(park_code, category)` → `data_cache/[PARK]/[YYYY-MM-DD]/[category].json`
- `load_daily_cache(park_code, category)` → Returns cached data or None
- `save_daily_cache(park_code, category, data)` → Saves to today's cache file

**File: `app/orchestrator.py`**
Updated `handle_query` to use cache-first approach:
```python
# Alerts
alerts_data = self.data_manager.load_daily_cache(intent.park_code, "alerts")
if alerts_data is not None:
    alerts = [Alert(**a) for a in alerts_data]
else:
    alerts = self.nps.get_alerts(intent.park_code)
    self.data_manager.save_daily_cache(intent.park_code, "alerts", [a.model_dump() for a in alerts])
```
Same pattern for `events` and `weather`.

---

## 4. Critical Bug Fixes

### 4.1 Missing `weather` Parameter
**Problem:** Weather always showed "unavailable" even when cached.
**Root Cause:** `generate_response` call in `orchestrator.py` was missing `weather=weather` argument.
**Fix:** Added `weather=weather` to the call.

### 4.2 Missing `alerts` Parameter  
**Problem:** Alert URLs weren't accessible to the LLM.
**Root Cause:** Only `safety.reason` (list of strings) was passed, not the actual `Alert` objects.
**Fix:**
- Added `alerts: List[Any]` parameter to `generate_response` in `llm_service.py`
- Added `alerts=alerts` to call in `orchestrator.py`
- Updated `_build_data_context` to format alerts with URLs:
```python
def format_alert(a):
    alert_url = getattr(a, 'url', None)
    return link(a.title, alert_url)
```

### 4.3 Missing `Alert` Import
**Problem:** `NameError: name 'Alert' is not defined` when querying Zion.
**Fix:** Added `Alert` to imports in `orchestrator.py`:
```python
from app.models import ..., Alert
```

### 4.4 Park Code Normalization
**Problem:** LLM returned "yosemite" instead of "yose", causing cache to go to wrong folder.
**Fix:** Added normalization map in `orchestrator.py`:
```python
PARK_NAME_TO_CODE = {
    "yosemite": "yose",
    "zion": "zion",
    "grand canyon": "grca",
}
if intent.park_code:
    normalized = PARK_NAME_TO_CODE.get(intent.park_code.lower(), intent.park_code.lower())
    intent.park_code = normalized
```

### 4.5 False "No-Go" Status
**Problem:** Road closure alerts like "Tioga Road (through the park) closed" triggered "No-Go" because it contained "park" and "closed".
**Fix:** Changed logic in `constraints.py` to require explicit phrases:
```python
park_closed_phrases = ["park closed", "park is closed", "national park closed"]
is_park_closed = any(phrase in title_lower for phrase in park_closed_phrases)
```

### 4.6 Output Formatting
**Problem:** Status, Weather, and Alerts appeared on same line.
**Fix:** Updated LLM prompt template to put each on separate line with proper markdown.

---

## 5. All Alerts Now Shown

### Problem
Non-critical alerts were being filtered out in `ConstraintEngine.analyze_safety`.

### Solution
**File: `app/engine/constraints.py`**
- Changed to always append alert to `reasons` list
- Still categorize as "Critical Alert:" or "Safety Alert:" based on keywords
- But never filter out any alert

---

## Files Modified

| File | Changes |
|------|---------|
| `app/models.py` | Added `nps_url`, `alltrails_url`, `url` property to `TrailSummary` |
| `app/orchestrator.py` | Trail filtering relaxation, daily caching, weather/alerts passthrough, park code normalization, Alert import |
| `app/services/data_manager.py` | Daily cache methods (`load_daily_cache`, `save_daily_cache`) |
| `app/services/llm_service.py` | Added `alerts` parameter, updated `_build_data_context`, fixed prompt formatting |
| `app/engine/constraints.py` | Relaxed alert filtering, fixed No-Go logic |

---

## Cache Structure

```
data_cache/
├── ZION/
│   └── 2026-01-06/
│       ├── weather.json
│       ├── alerts.json
│       └── events.json
└── YOSE/
    └── 2026-01-06/
        ├── weather.json
        ├── alerts.json
        └── events.json
```

---

## Testing Notes

1. **Trail URLs**: Ask "Tell me about Pa'rus Trail" → Expect clickable links
2. **Weather Display**: Ask "Tell me about Zion" → Should show actual temperature
3. **Alert URLs**: Alerts should have clickable links
4. **Caching**: Check `data_cache/` folder for dated JSON files
5. **Status Logic**: Road closures → "Caution", Park closed → "No-Go"
