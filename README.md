
# Outdoor Adventure Concierge - Project Plan

**Goal:** Build a context-aware, real-time dashboard for National Park visitors that cross-references live alerts, vetted trail data, and zoned weather to generate safe, actionable itineraries.

**Architecture:**
*   **Frontend:** Streamlit (Two Tabs: Concierge Chat, Park Explorer)
*   **Backend:** Python Orchestrator with RAG & Constraint Engine
*   **Data Stack:** NPS API, AllTrails Scrape/LLM, WeatherAPI, Serper (Amenities), Firecrawl (Photo Blogs)

***

### Phase 0: Data Discovery & Fixtures (COMPLETE)
- [x] **Setup:** Project skeleton, `.env`, `requirements.txt`, `data_samples`.
- [x] **Fixtures:** Scripts to fetch/save raw JSON for YOSE, ZION, GRCA.
- [x] **Phase 0.5:** AllTrails Validated Scrape & Local LLM strategy.
- [x] **Feature Feasibility Sprint:**
    - [x] Amenities: Approved Serper API.
    - [x] Photography: Approved Firecrawl Scrape.

### Phase 1: Canonical Models & Adapters (COMPLETE)
- [x] **Step 1: Define Models (`app/models.py`)**
    - [x] `ParkContext` (Location, hours, contacts), `TrailSummary`.
    - [x] `Alert`, `Event`, `WeatherSummary`.
    - [x] `Amenity`, `PhotoSpot` (Updated with `lat`/`lon`/`rating_count`/`website`/`phone`).
    - [x] **Expanded Scope:** `Campground`, `VisitorCenter`, `Webcam`, `Place`, `ThingToDo`, `PassportStamp`.
- [x] **Step 2: NPS Adapter (`app/adapters/nps_adapter.py`)**
    - [x] Robust parsing for all core and expanded NPS entities.
- [x] **Step 3: Weather Adapter (`app/adapters/weather_adapter.py`)**
    - [x] Parser for WeatherAPI Forecasts, Alerts, Sunrise/Sunset.
- [x] **Step 4: External Adapters (`app/adapters/external_adapter.py`)**
    - [x] Parser for Firecrawl (Trails/Photos) and Serper (Amenities/Maps).

### Phase 2: Source Clients & Constraints (COMPLETE)
- [x] **Step 1: NPS Client (`app/clients/nps_client.py`)**
    - [x] Robust HTTP Wrapper with Retry/Timeout logic (`BaseClient`).
    - [x] Methods for `get_park_details`, `get_alerts`, `get_events`.
    - [x] **Expanded Methods:** `get_campgrounds`, `get_webcams`, `get_visitor_centers`, `get_places`, `get_things_to_do`.
- [x] **Step 2: Weather & External Clients**
    - [x] `WeatherClient`: Connects to WeatherAPI -> `WeatherSummary`.
    - [x] `ExternalClient`: Connects to Serper Maps Endpoint -> `List[Amenity]` with coordinate-based queries.
- [x] **Step 3: Constraint Engine (`app/engine/constraints.py`)**
    - [x] **User Context:** Defined `UserPreference` (Dogs, Mobility, Difficulty, Time).
    - [x] **Filter Logic:** `filter_trails` rejects options based on difficulty/length/pets.
    - [x] **Safety Logic:** `analyze_safety` triggers "No-Go" on extreme heat/cold or Park Closures.
- [x] **Step 4: Phase 2 Verification (`verify_phase2.py`)**
    - [x] Proven End-to-End: Fetched Live Data -> Applied User Prefs -> Generated Vetted Itinerary.

### Phase 3: The Orchestrator (COMPLETE)
- [x] **Step 1: LLM Service (`app/services/llm_service.py`)**
    - [x] **Migration to `google-genai` SDK:** Updated to v1.0.
    - [x] **Agentic Pattern:** Implemented specialized `AgentWorker` classes.
    - [x] **Intent Parsing:** Robust JSON extraction for `UserPreference`, `ParkCode`, etc.
    - [x] **Data Context:** Formatted strings for all major entities.
- [x] **Step 2: Orchestrator Logic (`app/orchestrator.py`)**
    - [x] **Pipeline:** Query -> Intent -> Parallel Data Fetch -> Constraints -> Agent Response.
    - [x] **Smart Amenities (Refactored):** Implemented `get_park_amenities` using `mine_entrances` + `DataManager`.
    - [x] **Context Management:** `SessionContext` handles multi-turn conversations.
- [x] **Step 3: Data Persistence Layer (NEW)**
    - [x] **`DataManager` Service:** Handles reading/writing cached JSON fixtures to `data_samples/ui_fixtures`.
    - [x] **`Geospatial` Utility:** `mine_entrances` logic with Haversine distance, Entrance/VC dominance rules, and outlier filtering.
    - [x] **Admin Tool:** `admin_fetch_amenities.py` to pre-populate park data (Zion, Yose, etc.) without runtime API costs.
    - [x] **Refiner Script:** `refine_amenities.py` to calculate distances and generate consolidated "Top 5" lists per hub.

### Phase 4: Streamlit UI (PENDING)
- [ ] **Step 1: App Skeleton & State**
    - [ ] `main.py` entry point with Sidebar (Park Selector, Date Picker).
    - [ ] Initialize `OutdoorConciergeOrchestrator` using `st.cache_resource`.
- [ ] **Step 2: Park Explorer Tab**
    - [ ] **Amenities Dashboard:** Display the "Top 5" Consolidated Amenities (Gas, Food, Medical) grouped by Entrance.
    - [ ] **Map Visualization:** Plot Park Entrances and key amenities using `st.map` or Folium.
    - [ ] **Trail Browser:** Sortable DataFrame of trails.
- [ ] **Step 3: Concierge Chat Tab**
    - [ ] Chat Interface (`st.chat_message`).
    - [ ] Orchestrator integration for RAG-based trip planning.

### Phase 5: RAG Refinement
- [ ] **Vector DB Ingest:** Things to Do, Trail Descriptions.
- [ ] **RAG Lookup:** Allow chat to answer specific history/nature questions.

### Phase 6: Production
- [ ] **Deployment:** Dockerfile & Cloud Run setup.
- [ ] **Hardening:** Error boundaries and production logging.

