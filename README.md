# ⛰️ Outdoor Adventure Concierge

> **Your AI-powered guide for national park planning, trail discovery, and real-time conditions.**

An intelligent trip planning assistant that combines official National Park Service data, live weather forecasts, community reviews, and Google Gemini AI to help you explore America's national parks safely and confidently.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)
![Gemini](https://img.shields.io/badge/Google%20Gemini-AI-orange.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## ✨ Features

### 🤠 AI Park Ranger (Chat Interface)
- **Context-aware conversations** powered by Google Gemini
- Ask natural questions like *"What are the best kid-friendly trails in Zion?"*
- All park data (trails, weather, alerts, amenities, reviews) passed as context for intelligent responses
- Multi-turn conversation with session memory
- Safety-aware responses based on current conditions and alerts

### 🔭 Park Explorer (Data Browser)

#### 🌡️ Weather Intelligence
- Current conditions with real-time updates
- **Weather by elevation zone** - know conditions at different altitudes
- 3-day forecasts with rain probability
- Sunrise/sunset times for planning
- Active weather alerts and warnings

#### 🥾 Trail Browser
- **Top-rated trails** with detailed cards, images, and descriptions
- **Filter by difficulty**: Easy, Moderate, Strenuous
- **Kid-friendly trails** identification
- **Wheelchair accessible** trails
- **Dog-friendly** options
- AllTrails rankings and ratings integrated
- Direct links to NPS and AllTrails pages

#### 📸 Photo Spots
- Best photography locations with optimal times
- Seasonal recommendations
- Composition tips from travel blogs
- AI-extracted insights from photography guides

#### 🚗 Scenic Drives
- Top-rated drives with highlights
- Distance and drive time estimates
- Key viewpoints and stops
- Best times to visit

#### 📅 Events & Activities
- Ranger programs and guided tours
- Upcoming park events
- Things to do beyond hiking
- Reservation requirements noted

#### 📹 Live Webcams
- Real-time park views
- Check current conditions before you go

#### 🏕️ Park Essentials
- Campgrounds with reservation links
- Visitor centers with hours
- Park alerts and closures

#### 🛒 Amenities
- **In-Park**: Restrooms, water, facilities
- **Nearby Services**:
  - ⛽ Gas stations
  - 🔌 EV charging stations
  - 🏥 Medical care / Urgent care
  - 🛒 Grocery stores
  - 🍽️ Restaurants

#### ⭐ Latest Reviews
- Fresh reviews scraped from AllTrails
- User photos included
- Current trail conditions from recent hikers

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Streamlit UI (main.py)                       │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │   AI Park Ranger    │    │       Park Explorer             │ │
│  │   (Chat Interface)  │    │   (Trails, Weather, etc.)       │ │
│  └──────────┬──────────┘    └──────────────┬──────────────────┘ │
└─────────────┼──────────────────────────────┼────────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Orchestrator Layer                           │
│  • Request handling    • Service coordination                   │
│  • Context management  • Response generation                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
       ▼                       ▼                       ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  LLM Service │    │ Constraint Engine│    │   Data Manager   │
│  (Gemini AI) │    │ (Filters/Safety) │    │   (Caching)      │
└──────┬───────┘    └──────────────────┘    └────────┬─────────┘
       │                                             │
       ▼                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Client Layer                           │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐ │
│  │ NPS Client│  │ Weather   │  │ Serper    │  │ Review Scraper│ │
│  │           │  │ Client    │  │ Client    │  │ (Firecrawl)   │ │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └───────┬───────┘ │
└────────┼──────────────┼──────────────┼────────────────┼─────────┘
         │              │              │                │
         ▼              ▼              ▼                ▼
    ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌─────────────┐
    │ NPS API │   │ Weather  │   │ Serper   │   │  AllTrails  │
    │         │   │ API      │   │ Maps API │   │ (Firecrawl) │
    └─────────┘   └──────────┘   └──────────┘   └─────────────┘
```

### Key Technologies
- **Frontend**: Streamlit with custom CSS styling
- **AI/LLM**: Google Gemini (intent parsing, response generation, data extraction)
- **Data Validation**: Pydantic models (25+ schemas)
- **APIs**: NPS API, WeatherAPI.com, Serper Maps, Firecrawl

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- API Keys for:
  - [Google Gemini](https://aistudio.google.com/app/apikey)
  - [National Park Service](https://www.nps.gov/subjects/developer/get-started.htm)
  - [WeatherAPI.com](https://www.weatherapi.com/)
  - [Serper](https://serper.dev/) (for amenities)
  - [Firecrawl](https://firecrawl.dev/) (for reviews, optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/outdoor_concierge.git
cd outdoor_concierge

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables

Create a `.env` file with the following:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key
NPS_API_KEY=your_nps_api_key
WEATHER_API_KEY=your_weather_api_key

# Optional (for full functionality)
SERPER_API_KEY=your_serper_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key

# Optional (defaults shown)
GEMINI_MODEL=gemini-3-flash-preview
```

### Running the App

```bash
streamlit run main.py
```

The app will open at `http://localhost:8501`

---

## 📁 Project Structure

```
outdoor_concierge/
├── main.py                     # Streamlit app entry point
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (not in git)
│
├── app/
│   ├── orchestrator.py         # Central request handling
│   ├── models.py               # Pydantic data models (25+)
│   ├── config.py               # Supported parks, settings
│   │
│   ├── services/
│   │   ├── llm_service.py      # Gemini AI integration
│   │   ├── data_manager.py     # File-based caching
│   │   ├── park_data_fetcher.py # On-demand data fetching
│   │   └── review_scraper.py   # AllTrails review scraping
│   │
│   ├── clients/
│   │   ├── nps_client.py       # National Park Service API
│   │   ├── weather_client.py   # WeatherAPI.com
│   │   └── external_client.py  # Serper Maps
│   │
│   ├── adapters/
│   │   ├── nps_adapter.py      # Parse NPS responses
│   │   ├── weather_adapter.py  # Parse weather data
│   │   └── alltrails_adapter.py # Parse trail data
│   │
│   ├── engine/
│   │   └── constraints.py      # Trail filtering, safety analysis
│   │
│   └── ui/
│       ├── components.py       # Reusable UI components
│       ├── styles.py           # CSS injection
│       ├── data_access.py      # Data loading utilities
│       └── views/              # Explorer tab views
│           ├── park_explorer_essentials.py
│           ├── park_explorer_trails.py
│           ├── park_explorer_photos.py
│           ├── park_explorer_drives.py
│           ├── park_explorer_activities.py
│           ├── park_explorer_events.py
│           └── park_explorer_webcams.py
│
├── data_samples/               # Cached park data
│   └── ui_fixtures/            # Per-park JSON files
│       └── {park_code}/
│           ├── park_details.json
│           ├── trails_v2.json
│           ├── photo_spots.json
│           ├── scenic_drives.json
│           └── ...
│
├── data_cache/                 # Daily volatile data cache
│   └── {park_code}/{date}/
│       ├── weather.json
│       ├── alerts.json
│       └── events.json
│
├── scripts/                    # Data fetching utilities
└── notes/                      # Documentation & diagrams
```

---

## 🏞️ Supported Parks

The app supports **63 US National Parks**. Parks with full data (trails, photos, drives, amenities):

| Park | Code | Status |
|------|------|--------|
| Bryce Canyon | `brca` | ✅ Full data |
| Grand Canyon | `grca` | ✅ Full data |
| Yosemite | `yose` | ✅ Full data |
| Zion | `zion` | ✅ Full data |
| *All others* | - | Basic data (fetch on-demand) |

New parks can have their data fetched directly from the Park Explorer tab.

---

## 📊 Data Sources

| Data Type | Source | Refresh |
|-----------|--------|---------|
| Park Details | NPS API | Static |
| Trails | NPS + Gemini enrichment | Static |
| Weather | WeatherAPI.com | Daily |
| Alerts | NPS API | Daily |
| Events | NPS API | Daily |
| Amenities | Serper Maps | Static |
| Reviews | AllTrails (Firecrawl) | On-demand |
| Photo Spots | Blogs (Gemini extraction) | Static |
| Scenic Drives | Blogs (Gemini extraction) | Static |

---

## 🧠 How AI is Used

### 1. Intent Parsing
Gemini parses natural language queries to extract:
- Target park
- User preferences (difficulty, kid-friendly, etc.)
- Response type (itinerary, trail list, safety info)

### 2. Context Injection
All relevant data is passed to Gemini as context:
- Filtered trails based on user preferences
- Current weather by elevation zone
- Active alerts and closures
- Nearby amenities
- Recent reviews with photos
- Photo spots and scenic drives

### 3. Response Generation
Gemini generates context-aware responses that:
- Reference specific trails with accurate data
- Include safety warnings when appropriate
- Provide actionable recommendations

### 4. Data Extraction
Gemini extracts structured data from:
- NPS descriptions → trail difficulty, distance, elevation
- Blog posts → photo spots, scenic drives
- AllTrails pages → reviews, conditions

---

## 🛠️ Development

### Running Tests

```bash
pytest tests/
```

### Adding a New Park

1. Data will be fetched automatically when you select a park in Park Explorer
2. Click "Fetch Park Data" to populate trails, photos, drives, etc.
3. Data is cached locally for future use

### Key Files to Understand

| File | Purpose |
|------|---------|
| `orchestrator.py` | Central coordination, start here |
| `llm_service.py` | Gemini integration, prompts |
| `models.py` | All Pydantic schemas |
| `constraints.py` | Trail filtering logic |

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [National Park Service](https://www.nps.gov/) for their comprehensive API
- [WeatherAPI.com](https://www.weatherapi.com/) for weather data
- [Google Gemini](https://ai.google.dev/) for AI capabilities
- [Streamlit](https://streamlit.io/) for the UI framework
- [AllTrails](https://www.alltrails.com/) for trail community data

---

<p align="center">
  <strong>Happy Trails! 🥾⛰️🏕️</strong>
</p>
