# Outdoor Adventure Concierge — Project Plan (Updated)

**Goal:** Build a context-aware dashboard for National Park visitors that cross-references live alerts, enriched trails, and zoned weather to generate safe, actionable itineraries.

**Architecture:**
- **Frontend:** Streamlit (Two Tabs: Concierge Chat, Park Explorer).
- **Backend:** Python Orchestrator with RAG + Constraint Engine.
- **Data Stack:** NPS API (official), Weather API (live), Serper (amenities + blog discovery), Firecrawl (scrape), Gemini (structured extraction/enrichment).

***

## Phase 0: Data discovery & fixtures (COMPLETE)
- [x] Setup project skeleton, `.env`, `requirements.txt`, and `data_samples/`.
- [x] Built initial fixtures approach for YOSE, ZION, GRCA.
- [x] Feasibility approved:
  - [x] Amenities via Serper.
  - [x] Photography via Firecrawl.

***

## Phase 1: Canonical models & adapters (COMPLETE)
- [x] Define models (`app/models.py`):
  - [x] `ParkContext`, `TrailSummary`.
  - [x] `Alert`, `Event`, `WeatherSummary`.
  - [x] `Amenity`, `PhotoSpot`.
  - [x] Expanded scope models: `Campground`, `VisitorCenter`, `Webcam`, `Place`, `ThingToDo`, `PassportStamp`.
- [x] NPS Adapter (`app/adapters/nps_adapter.py`): robust parsing for core + expanded entities.
- [x] Weather Adapter (`app/adapters/weather_adapter.py`): forecast parsing + alerts + sunrise/sunset.
- [x] External Adapter (`app/adapters/external_adapter.py`): Serper (amenities) and Firecrawl outputs.

***

## Phase 2: Source clients & constraints (COMPLETE)
- [x] NPS Client (`app/clients/nps_client.py`):
  - [x] Robust HTTP wrapper with retries/timeouts (`BaseClient`).
  - [x] Endpoints: park details, alerts, events, and expanded endpoints.
- [x] Weather + External clients:
  - [x] Weather client returns `WeatherSummary`.
  - [x] External client supports Serper Maps amenities queries returning `Amenity`.
- [x] Constraint engine (`app/engine/constraints.py`):
  - [x] User preference model + filtering (dogs/mobility/difficulty/time).
  - [x] Safety analysis (heat/cold/closures → “No-Go”).
- [x] Phase 2 end-to-end verification completed.

***

## Phase 3: Orchestrator & local-first data (COMPLETE)
- [x] LLM Service (`app/services/llm_service.py`):
  - [x] Migrated to `google-genai` (Gemini).
  - [x] Agent worker pattern + intent parsing + robust JSON extraction.
  - [x] Standardized Gemini config via `.env` (e.g., `GEMINI_API_KEY`, `GEMINI_MODEL`).
- [x] Orchestrator (`app/orchestrator.py`):
  - [x] Pipeline: query → intent → fetch → constraints → response generation.
  - [x] Context management (`SessionContext`) for multi-turn.
  - [x] Local-first orchestration: static entities load from `data_samples/ui_fixtures/` (cache-first), while volatile data stays live.
- [x] Data persistence layer:
  - [x] `DataManager` reads cached UI fixtures from `data_samples/ui_fixtures/`.
  - [x] `Geospatial` utilities support entrance mining and distance logic.
  - [x] Admin amenities fetch: `admin_fetch_amenities.py` mines hubs and calls Serper around hub coordinates.
  - [x] Amenities refiner: `refine_amenities.py` calculates distances and produces UI-ready “Top 5” lists per hub/category.
- [x] Consolidated static NPS fixture generation:
  - [x] Unified static NPS “freeze” workflow into `fetch_static_nps.py` (replacing redundant fetch scripts and raw/processed duplication).
  - [x] `app/weather_fetch.py` updated to use coordinates from `data_samples/ui_fixtures/{PARK}/park_details.json`.
  - [x] Removed redundant scripts / raw cache directory as part of cleanup.
- [x] Volatile data strategy (architectural decision):
  - [x] Do **not** persist Alerts/Events/Weather as durable fixtures; treat them as live-sync data.

***

## Phase 3.5: Trails golden dataset (COMPLETE)
- [x] **Core objective:** Convert legally safe but “marketing-poor” NPS data into a UI-grade “Golden Dataset” enabling filters like “Top 5 Easy Hikes” and “Wheelchair Friendly Views”.
- [x] **Link-Out strategy:**
  - [x] NPS remains source of truth for canonical trail records.
  - [x] AllTrails used only for popularity ranking + deep link (minimize scraping risk/cost).
  - [x] Gemini extracts hidden metadata (difficulty/accessibility/elevation/distance) from NPS descriptions.
- [x] **Generalized pipeline (multi-park):**
  - [x] Broad recall capture: `fetch_static_nps.py` pulls candidates from both **Places** and **Things To Do** to handle cross-park inconsistencies.
  - [x] Smart filtering: keyword-based broad classifier to avoid missing trails (e.g., “Trail”, “Hike”, “Narrows”, “Rim”).
  - [x] Gemini validation + enrichment: `refine_trails_with_gemini.py` validates “is this actually a hiking trail?” and extracts structured metrics.
- [x] **Ranking merger:**
  - [x] `fetch_rankings.py` pulls AllTrails hiking page markdown (Firecrawl), parses with Gemini into ranked list, then fuzzy-matches into local trails.
- [x] **Key issue resolutions included in pipeline:**
  - [x] “Canyon Overlook” rescue via schema-aware text concatenation + relaxed accept rules.
  - [x] Expanded ranking pool beyond Top 10 by extracting “Points of Interest” and assigning ranks 11+.
  - [x] Improved fuzzy matching normalization (strip “Trail/Trailhead”, normalize “Falls”/“Fall”).
- [x] **Final persisted artifact:** `data_samples/ui_fixtures/{PARK_CODE}/trails_v2.json` ready for UI consumption.

---

## Phase 3.6: Photo spots dataset (COMPLETE)
- [x] **Photo Spots functionality:** Auto-synthesize photography advice (best times, compositions, lens/crowd tips) from blog content into a structured dataset.
- [x] `fetch_photo_spots.py` pipeline:
  - [x] Search (Serper) for park-specific photography guides.
  - [x] Scrape (Firecrawl) blog posts into clean markdown/text.
  - [x] Extract (Gemini) structured PhotoSpot records (name, best time, tips, optional images).
  - [x] Save fixtures to `data_samples/ui_fixtures/{PARK_CODE}/photo_spots.json`.

***

## Phase 4: Streamlit UI (IN PROGRESS)

### Step 1: App Framework (COMPLETE)
- [x] `main.py` entrypoint with sidebar (park selector, date picker).
- [x] Initialize `OutdoorConciergeOrchestrator` with `st.cache_resource`.
- [x] **Volatile data caching:** Live fetch for Alerts/Events/Weather, cached per-user session.

### Step 2: Park Explorer - Core Views (COMPLETE)
- [x] **Static Loading:** Load fixtures from `data_samples/ui_fixtures/{PARK}/...` instantly.
- [x] **Amenities Dashboard:** 
  - [x] Folium map with custom icons (Green=EV, Blue=Gas, DarkRed=Medical).
  - [x] "Top 5" lists per hub/category.
  - [x] Distinct markers for Hubs vs Amenities.
- [x] **Trail Browser:**
  - [x] `trails_v2.json` loading with graceful error handling.
  - [x] Sidebar/Top-bar filters (Difficulty, Length, Accessibility, Pet-Friendly).

### Step 3: Feature Polish & Enrichment (COMPLETE)
- [x] **Trails UI Redesign:**
  - [x] **Top Rated Section:** Detailed cards with images, rank badges, and full descriptions.
  - [x] **Browse by Difficulty:** Compact 3-column grid for Easy/Moderate/Strenuous.
  - [x] **Map Legend:** Fixed bottom-left legend (Green/Orange/Red) with proper styling.
- [x] **Data Enrichment:**
  - [x] **Difficulty Inference:** Heuristic based on length/elevation/time when LLM fails.
  - [x] **Description Fallback Chain:** `clean_description` → `listingDescription` → `bodyText` → `img_alt`.
  - [x] **AllTrails Integration:** Regex fallbacks for missing time/elevation; merged fields into `trails_v2.json`.
- [x] **Pet-Friendly Feature:**
  - [x] Data Model: Added `is_pet_friendly` boolean.
  - [x] Extraction: Updated Gemini prompt for "pets allowed" keywords.
  - [x] UI: `🐕 Pet Friendly` checkbox and icons in trail cards.

### Step 4: Photo Spots (NEXT UP)
- [ ] Create `app/ui/views/park_explorer_photos.py`.
- [ ] Render grid/gallery of photo spots from `photo_spots.json`.
- [ ] Display Best Time tags and Photography Tips.

### Step 5: Park Essentials (NEW)
- [ ] **Weather Dashboard:** 3-day forecast, sunrise/sunset, current conditions.
- [ ] **Active Alerts:** Display active NPS alerts (Danger, Caution, Info) with collapsible details.
- [ ] **Things To Do:** Grid view of other activities (non-hiking) from `things_to_do.json`.
- [ ] **Events Calendar:** List upcoming park events from live API.

### Step 6: Concierge Chat (PENDING)
- [ ] `st.chat_message` UI + message history in `st.session_state`.
- [ ] Orchestrator integration for RAG-based itineraries and safety-aware answers.

***

## Phase 5: RAG refinement (PENDING)
- [ ] Vector DB ingest for things-to-do + trail descriptions.
- [ ] RAG lookup for history/nature Q&A in chat.

***

## Phase 6: Production (PENDING)
- [ ] Dockerfile + Cloud Run deployment.
- [ ] Hardening: error boundaries, production logging, rate-limit protections.
