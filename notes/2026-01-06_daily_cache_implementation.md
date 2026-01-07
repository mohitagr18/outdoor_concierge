# Daily Cache Implementation for Park Explorer

**Date:** 2026-01-06  
**Category:** Performance / Data Architecture

## Problem

When users navigated directly to Park Explorer without first using the chat, the app was re-querying APIs for weather, alerts, and events on every session/page refresh. This was inefficient and slow.

## Solution

Implemented a **daily disk cache** system that persists volatile data (weather, alerts, events) to disk, organized by park and date.

### Cache Structure
```
data_cache/
├── BRCA/
│   └── 2026-01-06/
│       ├── weather.json
│       ├── alerts.json
│       └── events.json
├── GRCA/
├── YOSE/
└── ZION/
```

## Files Modified

### 1. `app/ui/data_access.py`

**Changes:**
- Refactored `get_volatile_data()` to use daily disk cache via `DataManager`
- Added NPS API fallback for `park_details` when local fixtures don't exist
- Updated `clear_volatile_cache()` to delete today's cache directories

**Key Code:**
```python
def get_volatile_data(park_code: str, orchestrator) -> Dict[str, Any]:
    # Check daily cache first
    weather = data_manager.load_daily_cache(park_code, "weather")
    if weather:
        result["weather"] = weather
    else:
        # Fetch from API and save to cache
        w = orchestrator.weather.get_forecast(...)
        data_manager.save_daily_cache(park_code, "weather", w.model_dump())
```

---

### 2. `app/ui/views/park_explorer_essentials.py`

**Changes:**
- Updated `render_essentials_dashboard()` to accept `volatile_data` parameter
- Fixed weather data extraction to handle both flat (from cache) and nested (from API) formats

**Before:**
```python
def render_essentials_dashboard(park_code, orchestrator, static_data):
    volatile = st.session_state.get("volatile_cache", {})  # Session-only
```

**After:**
```python
def render_essentials_dashboard(park_code, orchestrator, static_data, volatile_data=None):
    weather = volatile_data.get("weather")  # From daily cache
```

---

### 3. `main.py`

**Changes:**
- Removed unused `volatile_cache` session state initialization
- Pass `volatile_data` to `render_essentials_dashboard()`
- Pass `nps_client` to `get_park_static_data()` for API fallback

---

### 4. `app/config.py`

**Changes:**
- Added Bryce Canyon (`brca`) to `SUPPORTED_PARKS` for testing

## Data Flow

```
┌─────────────────────┐
│   User selects park │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  get_volatile_data(park_code)       │
│  ┌───────────────────────────────┐  │
│  │ 1. Check disk cache           │  │
│  │    data_cache/PARK/DATE/*.json│  │
│  └───────────────────────────────┘  │
│              │                      │
│     Cache Hit│   Cache Miss         │
│              ▼          │           │
│     Return data         ▼           │
│              ┌───────────────────┐  │
│              │ 2. Fetch from API │  │
│              │ 3. Save to cache  │  │
│              └───────────────────┘  │
└─────────────────────────────────────┘
```

## Auto-Fetch for New Parks

When a park doesn't have local fixtures (e.g., `park_details.json`), the system now automatically fetches from the NPS API:

```python
def get_park_static_data(park_code: str, nps_client=None):
    park_raw = data_manager.load_fixture(park_code, "park_details.json")
    if park_raw:
        result["park_details"] = ParkContext(**park_raw)
    elif nps_client:
        # Fetch from NPS API
        park_context = nps_client.get_park_details(park_code)
```

This enables adding new parks to `SUPPORTED_PARKS` without manually creating fixture files.

## Testing

1. Verified cache hits in logs: `INFO:app.services.data_manager:Daily Cache HIT: data_cache/YOSE/2026-01-06/weather.json`
2. Added Bryce Canyon without fixtures - successfully fetched from API
3. Confirmed weather/alerts display correctly in Park Explorer

## Benefits

| Before | After |
|--------|-------|
| API called on every session | API called once per day per park |
| Data lost on browser refresh | Data persists for 24 hours |
| Slow initial load | Fast load from disk cache |
| Manual fixtures required | Auto-fetch from NPS API |
