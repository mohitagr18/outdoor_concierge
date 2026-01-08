# Dynamic Park Data Fetching Implementation

**Date:** 2026-01-08  
**Objective:** Enable dynamic data fetching for parks without pre-existing fixture data

---

## Overview

This document details the implementation of dynamic park data fetching for the Outdoor Concierge application. Previously, the app only worked with parks that had pre-populated data in `data_samples/ui_fixtures/`. After this implementation, the app can automatically fetch and process data for any supported park when a user selects it.

---

## Phase 1: Infrastructure Changes ✅

### 1.1 DataManager Enhancements
**File:** `app/services/data_manager.py`

Added two new methods:
- `save_fixture(park_code, filename, data)` - Saves data as JSON fixture, handles Pydantic models
- `has_fixture(park_code, filename)` - Checks if a fixture file exists

### 1.2 Script Refactoring for Programmatic Use

All data processing scripts were refactored from CLI-only to have callable functions:

| Script | New Function | Purpose |
|--------|-------------|---------|
| `refine_trails_with_gemini.py` | `refine_trails(park_code, progress_callback)` | Gemini enrichment of trail data |
| `refine_amenities.py` | `refine_amenities_for_park(park_code, data_dir)` | Consolidate amenity files |
| `fetch_rankings.py` | `fetch_and_merge_rankings(park_code, progress_callback)` | AllTrails scraping + merge |
| `fetch_photo_spots.py` | `fetch_photo_spots_for_park(park_code, progress_callback)` | Blog scraping for photo spots |
| `admin_fetch_amenities.py` | `fetch_amenities_for_park(park_code, ...)` | Google Maps amenity search |

### 1.3 ParkDataFetcher Service
**File:** `app/services/park_data_fetcher.py` [NEW]

Central orchestration service with methods:
- `has_basic_data(park_code)` - Check if park has minimum data
- `has_complete_data(park_code)` - Check if all fixtures exist
- `get_missing_fixtures(park_code)` - List missing files
- `fetch_nps_static_data(park_code)` - Fetch from NPS API
- `fetch_and_classify_trails(park_code)` - Prepare raw trail data
- `refine_trails(park_code)` - Run Gemini enrichment
- `fetch_rankings(park_code)` - AllTrails data
- `fetch_photo_spots(park_code)` - Blog scraping
- `fetch_amenities(park_code)` - Google Maps amenity search
- `ensure_park_data(park_code, ...)` - Main entry point, runs all needed steps

---

## Phase 2: Chat Flow Integration ✅

### 2.1 Orchestrator Changes
**File:** `app/orchestrator.py`

- Added `ParkDataFetcher` import and initialization
- Implemented save-on-fetch pattern: when NPS API is called as fallback, data is now saved to fixtures
- Created `load_or_fetch()` helper function for consistent caching behavior

### 2.2 Testing
- Browser test with ZION confirmed chat still works
- Response included weather (34.0°F), alerts, and park information

---

## Phase 3: Explorer Tab Integration ✅

### 3.1 Data Existence Check
**File:** `main.py`

Added logic before Explorer tab rendering:
1. Check if park has data using `ParkDataFetcher.has_basic_data()`
2. If missing, show warning message
3. Display "🚀 Fetch Park Data" button
4. Show progress bar during fetch
5. Display success/error messages
6. Auto-reload page when complete

### 3.2 Configuration
**File:** `app/config.py`

BRCA (Bryce Canyon) already present in `SUPPORTED_PARKS`

---

## Phase 4: Bug Fixes & Testing ✅

### 4.1 Trail Coordinates Bug
**Issue:** BRCA trails had `0,0` coordinates - map didn't show any markers

**Root Cause:** `refine_trails_with_gemini.py` was looking for `trail.latitude/longitude` fields, but raw data used `trail.location.lat/lon` structure

**Fix:** Updated lines 249-252 to handle both formats:
```python
"lat": float(trail.get("location", {}).get("lat", 0) or trail.get("latitude", 0) or 0),
"lon": float(trail.get("location", {}).get("lon", 0) or trail.get("longitude", 0) or 0)
```

**Result:** 55/60 BRCA trails now have valid coordinates

### 4.2 Missing Hub Services
**Issue:** Hub services (gas stations, restaurants, hospitals) not appearing for BRCA

**Root Cause:** Amenity fetching was not included in the automatic fetch flow - it was a separate admin script

**Fix:** 
1. Refactored `admin_fetch_amenities.py` with callable `fetch_amenities_for_park()` function
2. Added `fetch_amenities()` method to `ParkDataFetcher`
3. Enabled `include_amenities=True` by default in `ensure_park_data()`
4. Added to main.py ensure_park_data call

**Result:** 1 hub found for BRCA with all amenity categories

---

## Files Modified Summary

| File | Type | Changes |
|------|------|---------|
| `app/services/data_manager.py` | MODIFY | +`save_fixture()`, +`has_fixture()` |
| `app/services/park_data_fetcher.py` | NEW | Central orchestration service |
| `app/orchestrator.py` | MODIFY | +ParkDataFetcher, +save-on-fetch |
| `main.py` | MODIFY | +Data existence check, +fetch UI |
| `scripts/refine_trails_with_gemini.py` | MODIFY | +`refine_trails()`, fixed coords |
| `scripts/refine_amenities.py` | MODIFY | +`refine_amenities_for_park()` |
| `scripts/fetch_rankings.py` | MODIFY | +`fetch_and_merge_rankings()` |
| `scripts/fetch_photo_spots.py` | MODIFY | +`fetch_photo_spots_for_park()` |
| `scripts/admin_fetch_amenities.py` | MODIFY | +`fetch_amenities_for_park()` |

---

## Test Results

| Test | Result |
|------|--------|
| Unit tests (9 total) | ✅ All pass |
| Chat with ZION | ✅ Working |
| Explorer with YOSE (44 trails) | ✅ Working |
| BRCA trail coordinates | ✅ 55/60 with valid coords |
| BRCA amenities | ✅ 1 hub found |

---

## API Dependencies

The following APIs are used during data fetching:

| API | Purpose | Required For |
|-----|---------|--------------|
| NPS API | Park info, trails, campgrounds, etc. | All parks |
| Gemini API | Trail data enrichment | Trail refinement |
| Firecrawl API | Web scraping | AllTrails, photo spots |
| Serper API | Google Maps search | Amenities |

---

## Usage

### Adding a New Park

1. Ensure park code is in `app/config.py` `SUPPORTED_PARKS`
2. Add park to `PARK_URL_MAP` in `scripts/fetch_rankings.py` for AllTrails support
3. Add park to `PARK_NAME_MAP` in `scripts/fetch_photo_spots.py` for photo spots
4. Select park in app → Explorer tab → Click "🚀 Fetch Park Data"
5. Wait 2-5 minutes for all data to be fetched and processed

### Manual Data Refresh

To re-fetch data for a park:
```bash
# Delete existing fixtures
rm -rf data_samples/ui_fixtures/BRCA/

# Re-fetch via app or programmatically:
python -c "
from app.services.park_data_fetcher import ParkDataFetcher
from app.clients.nps_client import NPSClient

fetcher = ParkDataFetcher(nps_client=NPSClient())
fetcher.ensure_park_data('BRCA')
"
```
