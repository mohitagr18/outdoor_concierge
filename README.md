# 🌲 Outdoor Adventure Concierge - Project Plan

**Goal:** Build a context-aware, real-time dashboard for National Park visitors that cross-references live alerts, vetted trail data, and zoned weather to generate safe, actionable itineraries.

**Architecture:**
- **Frontend:** Streamlit (Two Tabs: "Concierge Chat" & "Park Explorer")
- **Backend:** Python Orchestrator with RAG & Constraint Engine
- **Data Stack:** NPS API, AllTrails (Scrape+LLM), WeatherAPI, Serper (Amenities), Firecrawl (Photo Blogs)

---

## 📅 Phase 0: Data Discovery & Fixtures (COMPLETE)
- [x] **Setup:** Project skeleton (`.env`, `requirements.txt`).
- [x] **Fixtures:** Scripts to fetch/save raw JSON for YOSE, ZION, GRCA (NPS & Weather).
- [x] **Phase 0.5 (AllTrails):** Validated "Scrape + Local LLM" strategy.
- [x] **Feature Feasibility Sprint:**
    - [x] **Amenities:** Approved (Serper API).
    - [x] **Photography:** Approved (Firecrawl Scrape).

## 🏗️ Phase 1: Canonical Models & Adapters (COMPLETE)
- [x] **Step 1: Define Models (`app/models.py`)**
    - [x] `ParkContext` (Location, hours, images, contacts)
    - [x] `TrailSummary` (Difficulty, stats, verified reviews, surface types)
    - [x] `Alert` & `Event` (Safety info, categories)
    - [x] `WeatherSummary` (Forecasts, sunrise/sunset, severe alerts)
    - [x] `Amenity` (Google Maps integration) & `PhotoSpot`
- [x] **Step 2: NPS Adapter (`app/adapters/nps_adapter.py`)**
    - [x] Parsers for `ParkContext`, `Alert`, `Event` with error handling.
- [x] **Step 3: Weather Adapter (`app/adapters/weather_adapter.py`)**
    - [x] Robust parser for WeatherAPI (handles variable string/dict fields).
- [x] **Step 4: External Adapters (`app/adapters/alltrails_adapter.py`)**
    - [x] Parser for Firecrawl+LLM trail data.
    - [x] Parser for Serper amenities.
- [x] **Step 5: Verification (`verify_phase1.py`)**
    - [x] Master script verified data integrity across all 3 sample parks.

## 🔌 Phase 2: Source Clients & Constraints (NEXT)
- [ ] **Step 1: NPS Client (`app/clients/nps_client.py`)**
    - [ ] Robust HTTP Wrapper (retry logic, timeouts).
    - [ ] `get_park_details(park_code)` -> `ParkContext`
    - [ ] `get_alerts(park_code)` -> `List[Alert]`
- [ ] **Step 2: Weather & External Clients (`app/clients/weather_client.py`)**
    - [ ] `WeatherClient`: Connects to WeatherAPI -> `WeatherSummary`.
    - [ ] `ExternalClient`: Connects to Serper (Amenities) & Firecrawl (Photo Cache).
- [ ] **Step 3: Constraint Engine (`app/engine/constraints.py`)**
    - [ ] **User Context:** Define schema for `UserPreference` (e.g., `has_dog`, `mobility_issues`, `time_available`).
    - [ ] **Filter Logic:** Implement `filter_trails()`, `filter_activities()`, and `check_safety_thresholds()`.
- [ ] **Step 4: Phase 2 Verification**
    - [ ] `verify_phase2.py`: Fetch "Live" (or Mocked) data -> Apply Constraints -> Print Vetted Results.

## 🤖 Phase 3: The Orchestrator
- [ ] **Orchestrator Logic (`app/orchestrator.py`):**
    1. Parse user query.
    2. Parallel fetch (NPS, Weather, Cache).
    3. Retrieve candidates (Trails, Activities).
    4. Apply Constraint Engine.
    5. Generate "Vetted Itinerary".

## 🖥️ Phase 4: Streamlit UI (Two-Tab Layout)
- [ ] **Tab 1: Concierge (Chat & Plan)**
    - [ ] **Chat Interface:** Interactive Q&A.
    - [ ] **"Go/No-Go" Header:** Dynamic safety status.
    - [ ] **Constraint Toggles:** Sidebar widgets (Kids, Pets).
- [ ] **Tab 2: Park Explorer (Browse)**
    - [ ] **Trail Board:** Filterable DataFrame.
    - [ ] **Amenities Map:** Google Maps links for Gas/Medical.
    - [ ] **Webcams & Live Intel.**

## 🧠 Phase 5: RAG & Refinement
- [ ] **Vector DB:** Ingest static "Things to Do" descriptions.
- [ ] **RAG Lookup:** Allow chat to answer nature/history questions.

## 🚀 Phase 6: Production
- [ ] **Caching:** SQLite/Redis for API rate limit protection.
- [ ] **Deployment:** Docker/Streamlit Cloud.
