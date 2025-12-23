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
    - [x] **Wildlife:** Rejected (Scraping unreliable; will use NPS Alerts).

## 🏗️ Phase 1: Canonical Models & Adapters (NEXT)
- [ ] **Step 1: Define Models (`app/models.py`)**
    - [ ] `ParkContext` (Location, hours)
    - [ ] `TrailSummary` (Difficulty, stats, features, recent reviews)
    - [ ] `Alert` & `Event` (Safety info)
    - [ ] `WeatherSummary` (Current + Forecast)
    - [ ] `Amenity` (Gas, Med, Grocery, EV - *New field: google_maps_link*)
    - [ ] `PhotoSpot` (Name, Best Time, Tips - *New Model*)
- [ ] **Step 2: NPS Adapter (`app/adapters/nps_adapter.py`)**
    - [ ] Functions to parse raw NPS JSON -> Pydantic Models.
- [ ] **Step 3: Weather Adapter (`app/adapters/weather_adapter.py`)**
    - [ ] Functions to parse `weather.json` -> `WeatherSummary`.
- [ ] **Step 4: AllTrails Adapter (`app/adapters/alltrails_adapter.py`)**
    - [ ] Reusable wrapper for Scrape+LLM logic.
- [ ] **Step 5: Verification Script**
    - [ ] Script to load all fixtures -> convert to Models -> print summary.

## 🔌 Phase 2: Source Clients & Constraints
- [ ] **NPS Client:** `get_live_alerts()`, `get_park_details()`.
- [ ] **Weather Client:** `get_forecast(lat, lon)`.
- [ ] **External Client (`app/clients/external.py`):** 
    - [ ] `get_amenities(lat, lon)` via Serper.
    - [ ] `get_photo_spots(park_name)` via Firecrawl (cached).
- [ ] **Constraint Engine:** Logic for filtering activities based on User Constraints (Pets, Kids, Mobility).

## 🤖 Phase 3: The Orchestrator
- [ ] **User Request Schema:** Define `UserContext` (Kids, Pets, Ability).
- [ ] **Orchestrator Logic:**
    1. Parse user query.
    2. Fetch live data (Alerts, Weather).
    3. Retrieve candidates (Trails, Activities, Photo Spots).
    4. Apply Constraint Engine.
    5. Generate "Vetted Itinerary".

## 🖥️ Phase 4: Streamlit UI (Two-Tab Layout)
- [ ] **Tab 1: Concierge (Chat & Plan)**
    - [ ] **Chat Interface:** Interactive Q&A with the Orchestrator.
    - [ ] **"Go/No-Go" Header:** Dynamic safety status (Green/Yellow/Red) based on Alerts/Weather.
    - [ ] **Vetted Itinerary:** Structured output recommending *specific* safe activities.
    - [ ] **Constraint Toggles:** Sidebar widgets to set "Has Dog", "Kids", "Accessibility".
- [ ] **Tab 2: Park Explorer (Browse)**
    - [ ] **🚨 Live Intel:** Banner for Critical Alerts & 3-Day Weather Forecast.
    - [ ] **🥾 Trail Board:** Sortable/Filterable DataFrame of vetted trails (Name, Difficulty, Status).
    - [ ] **📸 Photo Ops:** Grid of "Best Photo Spots" with "Best Time" tags.
    - [ ] **🍔 Amenities & Logistics:**
        - [ ] "Essential Services" Table (Urgent Care, Gas, Grocery) with Google Maps links.
        - [ ] Visitor Center & Campground status.
    - [ ] **👀 Webcams:** Live camera feed grid.

## 🧠 Phase 5: RAG & Refinement
- [ ] **Vector DB:** Ingest static "Things to Do" & "Places" descriptions.
- [ ] **RAG Lookup:** Allow chat to answer history/nature questions.
- [ ] **Optimization:** Cache heavy scrapes (AllTrails/Photography).

## 🚀 Phase 6: Production
- [ ] **Caching:** Implement caching (SQLite/Redis) to save API credits.
- [ ] **Deployment:** Dockerize or deploy to Streamlit Cloud.
