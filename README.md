# Outdoor Adventure Concierge — Project Plan (Updated)

**Goal:** Build a context-aware dashboard for National Park visitors that cross-references live alerts, enriched trails, and zoned weather to generate safe, actionable itineraries.[1]

**Architecture:**
- **Frontend:** Streamlit (Two Tabs: Concierge Chat, Park Explorer).[1]
- **Backend:** Python Orchestrator with RAG + Constraint Engine.[1]
- **Data Stack:** NPS API (official), Weather API (live), Serper (amenities + blog discovery), Firecrawl (scrape), Gemini (structured extraction/enrichment).[1]

***

## Phase 0: Data discovery & fixtures (COMPLETE)
- [x] Setup project skeleton, `.env`, `requirements.txt`, and `data_samples/`.[1]
- [x] Built initial fixtures approach for YOSE, ZION, GRCA.[1]
- [x] Feasibility approved:
  - [x] Amenities via Serper.[1]
  - [x] Photography via Firecrawl.[1]

***

## Phase 1: Canonical models & adapters (COMPLETE)
- [x] Define models (`app/models.py`):
  - [x] `ParkContext`, `TrailSummary`.[1]
  - [x] `Alert`, `Event`, `WeatherSummary`.[1]
  - [x] `Amenity`, `PhotoSpot`.[1]
  - [x] Expanded scope models: `Campground`, `VisitorCenter`, `Webcam`, `Place`, `ThingToDo`, `PassportStamp`.[1]
- [x] NPS Adapter (`app/adapters/nps_adapter.py`): robust parsing for core + expanded entities.[1]
- [x] Weather Adapter (`app/adapters/weather_adapter.py`): forecast parsing + alerts + sunrise/sunset.[1]
- [x] External Adapter (`app/adapters/external_adapter.py`): Serper (amenities) and Firecrawl outputs.[1]

***

## Phase 2: Source clients & constraints (COMPLETE)
- [x] NPS Client (`app/clients/nps_client.py`):
  - [x] Robust HTTP wrapper with retries/timeouts (`BaseClient`).[1]
  - [x] Endpoints: park details, alerts, events, and expanded endpoints.[1]
- [x] Weather + External clients:
  - [x] Weather client returns `WeatherSummary`.[1]
  - [x] External client supports Serper Maps amenities queries returning `Amenity`.[1]
- [x] Constraint engine (`app/engine/constraints.py`):
  - [x] User preference model + filtering (dogs/mobility/difficulty/time).[1]
  - [x] Safety analysis (heat/cold/closures → “No-Go”).[1]
- [x] Phase 2 end-to-end verification completed.[1]

***

## Phase 3: Orchestrator & local-first data (COMPLETE)
- [x] LLM Service (`app/services/llm_service.py`):
  - [x] Migrated to `google-genai` (Gemini).[1]
  - [x] Agent worker pattern + intent parsing + robust JSON extraction.[1]
  - [x] Standardized Gemini config via `.env` (e.g., `GEMINI_API_KEY`, `GEMINI_MODEL`).[1]
- [x] Orchestrator (`app/orchestrator.py`):
  - [x] Pipeline: query → intent → fetch → constraints → response generation.[1]
  - [x] Context management (`SessionContext`) for multi-turn.[1]
  - [x] Local-first orchestration: static entities load from `data_samples/ui_fixtures/` (cache-first), while volatile data stays live.[1]
- [x] Data persistence layer:
  - [x] `DataManager` reads cached UI fixtures from `data_samples/ui_fixtures/`.[1]
  - [x] `Geospatial` utilities support entrance mining and distance logic.[1]
  - [x] Admin amenities fetch: `admin_fetch_amenities.py` mines hubs and calls Serper around hub coordinates.[1]
  - [x] Amenities refiner: `refine_amenities.py` calculates distances and produces UI-ready “Top 5” lists per hub/category.[1]
- [x] Consolidated static NPS fixture generation:
  - [x] Unified static NPS “freeze” workflow into `fetch_static_nps.py` (replacing redundant fetch scripts and raw/processed duplication).[1]
  - [x] `app/weather_fetch.py` updated to use coordinates from `data_samples/ui_fixtures/{PARK}/park_details.json`.[1]
  - [x] Removed redundant scripts / raw cache directory as part of cleanup.[1]
- [x] Volatile data strategy (architectural decision):
  - [x] Do **not** persist Alerts/Events/Weather as durable fixtures; treat them as live-sync data.[1]

***

## Phase 3.5: Trails golden dataset (COMPLETE)
- [x] **Core objective:** Convert legally safe but “marketing-poor” NPS data into a UI-grade “Golden Dataset” enabling filters like “Top 5 Easy Hikes” and “Wheelchair Friendly Views”.[1]
- [x] **Link-Out strategy:**
  - [x] NPS remains source of truth for canonical trail records.[1]
  - [x] AllTrails used only for popularity ranking + deep link (minimize scraping risk/cost).[1]
  - [x] Gemini extracts hidden metadata (difficulty/accessibility/elevation/distance) from NPS descriptions.[1]
- [x] **Generalized pipeline (multi-park):**
  - [x] Broad recall capture: `fetch_static_nps.py` pulls candidates from both **Places** and **Things To Do** to handle cross-park inconsistencies.[1]
  - [x] Smart filtering: keyword-based broad classifier to avoid missing trails (e.g., “Trail”, “Hike”, “Narrows”, “Rim”).[1]
  - [x] Gemini validation + enrichment: `refine_trails_with_gemini.py` validates “is this actually a hiking trail?” and extracts structured metrics.[1]
- [x] **Ranking merger:**
  - [x] `fetch_rankings.py` pulls AllTrails hiking page markdown (Firecrawl), parses with Gemini into ranked list, then fuzzy-matches into local trails.[1]
- [x] **Key issue resolutions included in pipeline:**
  - [x] “Canyon Overlook” rescue via schema-aware text concatenation + relaxed accept rules.[1]
  - [x] Expanded ranking pool beyond Top 10 by extracting “Points of Interest” and assigning ranks 11+.[1]
  - [x] Improved fuzzy matching normalization (strip “Trail/Trailhead”, normalize “Falls”/“Fall”).[1]
- [x] **Final persisted artifact:** `data_samples/ui_fixtures/{PARK_CODE}/trails_v2.json` ready for UI consumption.[1]

---

## Phase 3.6: Photo spots dataset (COMPLETE)
- [x] **Photo Spots functionality:** Auto-synthesize photography advice (best times, compositions, lens/crowd tips) from blog content into a structured dataset.[1]
- [x] `fetch_photo_spots.py` pipeline:
  - [x] Search (Serper) for park-specific photography guides.[1]
  - [x] Scrape (Firecrawl) blog posts into clean markdown/text.[1]
  - [x] Extract (Gemini) structured PhotoSpot records (name, best time, tips, optional images).[1]
  - [x] Save fixtures to `data_samples/ui_fixtures/{PARK_CODE}/photo_spots.json`.[1]

***

## Phase 4: Streamlit UI (PENDING)
- [ ] Step 1: App skeleton & state
  - [ ] `main.py` entrypoint with sidebar (park selector, date picker).[1]
  - [ ] Initialize `OutdoorConciergeOrchestrator` with `st.cache_resource`.[1]
  - [ ] **Volatile data caching in UI:** Fetch Alerts/Events/Weather live, but cache them per-user session in `st.session_state` to prevent repeated API calls during UI reruns.[1]
- [ ] Step 2: Park Explorer tab
  - [ ] Load static fixtures from `data_samples/ui_fixtures/{PARK}/...` (instant).[1]
  - [ ] Amenities dashboard: show refined “Top 5” per hub/category.[1]
  - [ ] Map visualization: hubs + amenity pins (Plotly/Folium).[1]
  - [ ] Trail browser: use `trails_v2.json` with filters (difficulty, accessibility, ranked).[1]
  - [ ] Photo spots panel: show `photo_spots.json` with best-time + tips.[1]
- [ ] Step 3: Concierge Chat tab
  - [ ] `st.chat_message` UI + message history in `st.session_state`.[1]
  - [ ] Orchestrator integration for RAG-based itineraries and safety-aware answers.[1]

***

## Phase 5: RAG refinement (PENDING)
- [ ] Vector DB ingest for things-to-do + trail descriptions.[1]
- [ ] RAG lookup for history/nature Q&A in chat.[1]

***

## Phase 6: Production (PENDING)
- [ ] Dockerfile + Cloud Run deployment.[1]
- [ ] Hardening: error boundaries, production logging, rate-limit protections.[1]

--- 

