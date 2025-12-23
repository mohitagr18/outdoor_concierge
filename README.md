Here is the updated **Project Plan** reflecting our progress. We have successfully completed **Phase 0, 1, and 2** (including the expanded scope for Campgrounds, Webcams, etc.).

You can copy-paste this directly into your `README.md`.

***

# 🌲 Outdoor Adventure Concierge - Project Plan

**Goal:** Build a context-aware, real-time dashboard for National Park visitors that cross-references live alerts, vetted trail data, and zoned weather to generate safe, actionable itineraries.

**Architecture:**
- **Frontend:** Streamlit (Two Tabs: "Concierge Chat" & "Park Explorer")
- **Backend:** Python Orchestrator with RAG & Constraint Engine
- **Data Stack:** NPS API, AllTrails (Scrape+LLM), WeatherAPI, Serper (Amenities), Firecrawl (Photo Blogs)

***

## 📅 Phase 0: Data Discovery & Fixtures (COMPLETE)
- [x] **Setup:** Project skeleton (`.env`, `requirements.txt`, `data_samples/`).
- [x] **Fixtures:** Scripts to fetch/save raw JSON for YOSE, ZION, GRCA.
- [x] **Phase 0.5 (AllTrails):** Validated "Scrape + Local LLM" strategy.
- [x] **Feature Feasibility Sprint:**
    - [x] **Amenities:** Approved (Serper API).
    - [x] **Photography:** Approved (Firecrawl Scrape).

## 🏗️ Phase 1: Canonical Models & Adapters (COMPLETE)
- [x] **Step 1: Define Models (`app/models.py`)**
    - [x] `ParkContext` (Location, hours, contacts) & `TrailSummary`
    - [x] `Alert`, `Event`, `WeatherSummary`
    - [x] `Amenity`, `PhotoSpot`
    - [x] **Expanded Scope:** `Campground`, `VisitorCenter`, `Webcam`, `Place`, `ThingToDo`, `PassportStamp`
- [x] **Step 2: NPS Adapter (`app/adapters/nps_adapter.py`)**
    - [x] Robust parsing for all core and expanded NPS entities.
- [x] **Step 3: Weather Adapter (`app/adapters/weather_adapter.py`)**
    - [x] Parser for WeatherAPI (Forecasts, Alerts, Sunrise/Sunset).
- [x] **Step 4: External Adapters (`app/adapters/external_adapter.py`)**
    - [x] Parser for Firecrawl (Trails/Photos) and Serper (Amenities).

## 🔌 Phase 2: Source Clients & Constraints (COMPLETE)
- [x] **Step 1: NPS Client (`app/clients/nps_client.py`)**
    - [x] Robust HTTP Wrapper with Retry/Timeout logic (`BaseClient`).
    - [x] Methods for `get_park_details`, `get_alerts`, `get_events`.
    - [x] **Expanded Methods:** `get_campgrounds`, `get_webcams`, `get_visitor_centers`, etc.
- [x] **Step 2: Weather & External Clients**
    - [x] `WeatherClient`: Connects to WeatherAPI -> `WeatherSummary`.
    - [x] `ExternalClient`: Connects to Serper -> `List[Amenity]`.
- [x] **Step 3: Constraint Engine (`app/engine/constraints.py`)**
    - [x] **User Context:** Defined `UserPreference` (Dogs, Mobility, Difficulty, Time).
    - [x] **Filter Logic:** `filter_trails()` rejects options based on difficulty/length/pets.
    - [x] **Safety Logic:** `analyze_safety()` triggers "No-Go" on extreme heat/cold or Park Closures.
- [x] **Step 4: Phase 2 Verification (`verify_phase2.py`)**
    - [x] Proven End-to-End: Fetched Live Data -> Applied User Prefs -> Generated "Vetted Itinerary".

## 🤖 Phase 3: The Orchestrator (NEXT)
- [ ] **Step 1: LLM Service (`app/services/llm_service.py`)**
    - [ ] `parse_user_intent(query)`: Convert natural language -> `UserPreference` object.
    - [ ] `generate_response(data, status)`: Write a friendly, safety-aware answer.
- [ ] **Step 2: Orchestrator Logic (`app/orchestrator.py`)**
    - [ ] **Pipeline:** Query -> Intent -> Parallel Data Fetch -> Constraints -> Response.
    - [ ] **Context Management:** Handling "What about tomorrow?" follow-ups.
- [ ] **Step 3: Phase 3 Verification**
    - [ ] `verify_phase3.py`: Full CLI Chatbot experience.

## 🖥️ Phase 4: Streamlit UI
- [ ] **Tab 1: Concierge (Chat & Plan)**
    - [ ] Chat Interface (Streamlit Chat Elements).
    - [ ] "Go/No-Go" Header (Dynamic Safety Status).
    - [ ] Sidebar Config (Park Selection, Date Picker).
- [ ] **Tab 2: Park Explorer (Browse)**
    - [ ] Trail DataFrame with Filters.
    - [ ] Webcam Grid (Live Views).
    - [ ] Amenities Map.

## 🧠 Phase 5: RAG & Refinement
- [ ] **Vector DB:** Ingest "Things to Do" & Trail Descriptions.
- [ ] **RAG Lookup:** Allow chat to answer specific history/nature questions.

## 🚀 Phase 6: Production
- [ ] **Caching:** Redis/SQLite for API rate limit protection.
- [ ] **Deployment:** Dockerfile & Cloud Run setup.