# Outdoor Adventure Concierge - Architecture Diagrams

This document contains architecture diagrams for the Outdoor Adventure Concierge application. The diagrams are created in Mermaid syntax and provide both technical and executive-level views of the system.

---

## 1. Detailed Technical Architecture Diagram

This diagram shows the complete system architecture including all layers, services, API integrations, and data flows. Designed for technical stakeholders (developers, architects, DevOps).

```mermaid
flowchart TB
    subgraph UI["🖥️ Presentation Layer (Streamlit)"]
        direction TB
        MAIN["main.py<br/>App Entry Point"]
        
        subgraph TABS["Tab Views"]
            TAB_CHAT["AI Park Ranger<br/>(Chat Interface)"]
            TAB_EXPLORER["Park Explorer<br/>(Data Browser)"]
        end
        
        subgraph VIEWS["UI Views (app/ui/views/)"]
            V_ESSENTIALS["park_explorer_essentials.py"]
            V_TRAILS["park_explorer_trails.py"]
            V_PHOTOS["park_explorer_photos.py"]
            V_DRIVES["park_explorer_drives.py"]
            V_ACTIVITIES["park_explorer_activities.py"]
            V_EVENTS["park_explorer_events.py"]
            V_WEBCAMS["park_explorer_webcams.py"]
        end
        
        subgraph UI_SUPPORT["UI Support"]
            COMPONENTS["components.py<br/>(Reusable UI)"]
            STYLES["styles.py<br/>(CSS Injection)"]
            DATA_ACCESS["data_access.py<br/>(Data Loading)"]
        end
    end
    
    subgraph ORCHESTRATION["🎯 Orchestration Layer"]
        ORCH["OutdoorConciergeOrchestrator<br/>(orchestrator.py)"]
        
        subgraph ORCH_MODELS["Request/Response Models"]
            REQ["OrchestratorRequest"]
            RESP["OrchestratorResponse"]
            SESSION["SessionContext"]
        end
    end
    
    subgraph ENGINE["⚙️ Constraint Engine"]
        CONSTRAINTS["ConstraintEngine<br/>(engine/constraints.py)"]
        USER_PREF["UserPreference"]
        SAFETY["SafetyStatus"]
    end
    
    subgraph SERVICES["🔧 Service Layer"]
        direction TB
        subgraph LLM["LLM Service"]
            LLM_SVC["GeminiLLMService<br/>(llm_service.py)"]
            AGENT["AgentWorker"]
            INTENT["LLMParsedIntent"]
            LLM_RESP["LLMResponse"]
        end
        
        subgraph DATA_SVC["Data Services"]
            DATA_MGR["DataManager<br/>(data_manager.py)"]
            FETCHER["ParkDataFetcher<br/>(park_data_fetcher.py)"]
            SCRAPER["ReviewScraper<br/>(review_scraper.py)"]
        end
    end
    
    subgraph CLIENTS["📡 API Client Layer"]
        NPS_CLIENT["NPSClient<br/>(nps_client.py)"]
        WEATHER_CLIENT["WeatherClient<br/>(weather_client.py)"]
        EXTERNAL_CLIENT["ExternalClient<br/>(external_client.py)"]
        BASE_CLIENT["BaseClient<br/>(base_client.py)"]
    end
    
    subgraph ADAPTERS["🔄 Adapter Layer (Data Parsing)"]
        NPS_ADAPTER["nps_adapter.py<br/>(Parse NPS Responses)"]
        WEATHER_ADAPTER["weather_adapter.py<br/>(Parse Weather Data)"]
        EXTERNAL_ADAPTER["external_adapter.py<br/>(Parse Serper Data)"]
        ALLTRAILS_ADAPTER["alltrails_adapter.py<br/>(Parse Trail Data)"]
    end
    
    subgraph MODELS["📋 Domain Models (models.py + Pydantic)"]
        direction LR
        M_PARK["ParkContext"]
        M_TRAIL["TrailSummary"]
        M_WEATHER["WeatherSummary"]
        M_ALERT["Alert"]
        M_EVENT["Event"]
        M_CAMP["Campground"]
        M_VC["VisitorCenter"]
        M_WEBCAM["Webcam"]
        M_AMENITY["Amenity"]
        M_PHOTO["PhotoSpot"]
        M_DRIVE["ScenicDrive"]
    end
    
    subgraph STORAGE["💾 Data Storage"]
        subgraph STATIC["Static Data (data_samples/)"]
            FIXTURES["ui_fixtures/<br/>Per-Park JSON"]
            RAW_NPS["nps/raw/<br/>Raw API Responses"]
        end
        
        subgraph VOLATILE["Volatile Data (data_cache/)"]
            DAILY["[PARK]/[DATE]/<br/>weather.json<br/>alerts.json<br/>events.json"]
        end
    end
    
    subgraph EXTERNAL["🌐 External APIs"]
        API_NPS["National Park Service API<br/>(developer.nps.gov)"]
        API_WEATHER["WeatherAPI.com<br/>(weather + forecasts)"]
        API_SERPER["Serper Maps API<br/>(amenities search)"]
        API_GEMINI["Google Gemini API<br/>(AI/LLM)"]
        API_FIRECRAWL["Firecrawl API<br/>(web scraping)"]
        API_DDG["DuckDuckGo<br/>(URL discovery)"]
    end
    
    %% UI Flow
    MAIN --> TABS
    TAB_EXPLORER --> VIEWS
    VIEWS --> UI_SUPPORT
    TAB_CHAT --> ORCH
    
    %% Orchestration Flow
    ORCH --> LLM_SVC
    ORCH --> CONSTRAINTS
    ORCH --> DATA_MGR
    ORCH --> FETCHER
    ORCH --> NPS_CLIENT
    ORCH --> WEATHER_CLIENT
    ORCH --> EXTERNAL_CLIENT
    
    %% Service Dependencies
    LLM_SVC --> API_GEMINI
    LLM_SVC --> AGENT
    FETCHER --> NPS_CLIENT
    FETCHER --> DATA_MGR
    SCRAPER --> API_FIRECRAWL
    SCRAPER --> API_DDG
    SCRAPER --> LLM_SVC
    
    %% Client to API
    NPS_CLIENT --> API_NPS
    WEATHER_CLIENT --> API_WEATHER
    EXTERNAL_CLIENT --> API_SERPER
    NPS_CLIENT --> BASE_CLIENT
    WEATHER_CLIENT --> BASE_CLIENT
    EXTERNAL_CLIENT --> BASE_CLIENT
    
    %% Client to Adapter
    NPS_CLIENT --> NPS_ADAPTER
    WEATHER_CLIENT --> WEATHER_ADAPTER
    EXTERNAL_CLIENT --> EXTERNAL_ADAPTER
    SCRAPER --> ALLTRAILS_ADAPTER
    
    %% Adapter to Models
    NPS_ADAPTER --> MODELS
    WEATHER_ADAPTER --> MODELS
    EXTERNAL_ADAPTER --> MODELS
    ALLTRAILS_ADAPTER --> MODELS
    
    %% Data Flow
    DATA_MGR --> STORAGE
    DATA_ACCESS --> DATA_MGR
    
    %% Styling
    classDef ui fill:#e1f5fe,stroke:#01579b
    classDef orch fill:#fff3e0,stroke:#e65100
    classDef service fill:#e8f5e9,stroke:#2e7d32
    classDef client fill:#fce4ec,stroke:#c2185b
    classDef adapter fill:#f3e5f5,stroke:#7b1fa2
    classDef storage fill:#fff8e1,stroke:#f57f17
    classDef external fill:#e3f2fd,stroke:#1565c0
    classDef model fill:#f5f5f5,stroke:#424242
    
    class MAIN,TAB_CHAT,TAB_EXPLORER,V_ESSENTIALS,V_TRAILS,V_PHOTOS,V_DRIVES,V_ACTIVITIES,V_EVENTS,V_WEBCAMS,COMPONENTS,STYLES,DATA_ACCESS ui
    class ORCH,REQ,RESP,SESSION orch
    class LLM_SVC,AGENT,INTENT,LLM_RESP,DATA_MGR,FETCHER,SCRAPER service
    class NPS_CLIENT,WEATHER_CLIENT,EXTERNAL_CLIENT,BASE_CLIENT client
    class NPS_ADAPTER,WEATHER_ADAPTER,EXTERNAL_ADAPTER,ALLTRAILS_ADAPTER adapter
    class FIXTURES,RAW_NPS,DAILY storage
    class API_NPS,API_WEATHER,API_SERPER,API_GEMINI,API_FIRECRAWL,API_DDG external
```

### Technical Layer Description

| Layer | Purpose | Key Files |
|-------|---------|-----------|
| **Presentation** | Streamlit UI with tabs for AI chat and data exploration | `main.py`, `app/ui/views/*.py` |
| **Orchestration** | Central request handling, coordinates all services | `orchestrator.py` |
| **Constraint Engine** | Trail filtering, safety analysis based on preferences | `engine/constraints.py` |
| **Services** | Business logic: LLM integration, data management, scraping | `services/*.py` |
| **Clients** | HTTP communication with external APIs | `clients/*.py` |
| **Adapters** | Transform raw API responses to domain models | `adapters/*.py` |
| **Models** | Pydantic data models for type safety | `models.py` |
| **Storage** | File-based JSON storage with daily caching | `data_samples/`, `data_cache/` |

---

## 2. High-Level Executive Architecture Diagram

This simplified diagram is designed for non-technical senior directors and C-suite executives. It focuses on business value, major components, and data sources without implementation details.

```mermaid
flowchart LR
    subgraph USER["👤 User Experience"]
        direction TB
        CHAT["💬 AI Park Ranger<br/><i>Ask questions, get recommendations</i>"]
        EXPLORE["🔭 Park Explorer<br/><i>Browse trails, photos, drives</i>"]
    end
    
    subgraph CORE["🧠 Intelligent Core"]
        direction TB
        AI["🤖 AI Assistant<br/><i>Powered by Google Gemini</i>"]
        SMART["⚡ Smart Engine<br/><i>Personalized recommendations<br/>Safety analysis</i>"]
    end
    
    subgraph DATA["📊 Data Hub"]
        direction TB
        CACHE["💾 Local Cache<br/><i>Fast access to park data</i>"]
    end
    
    subgraph SOURCES["🌐 Data Sources"]
        direction TB
        NPS["🏛️ National Park Service<br/><i>Official park information</i>"]
        WEATHER["🌤️ Weather Service<br/><i>Real-time conditions</i>"]
        MAPS["🗺️ Maps & Places<br/><i>Nearby amenities</i>"]
        REVIEWS["⭐ Trail Reviews<br/><i>Community insights</i>"]
    end
    
    USER --> CORE
    CORE --> DATA
    DATA --> SOURCES
    
    classDef userBox fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef coreBox fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef dataBox fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    classDef sourceBox fill:#fce4ec,stroke:#d81b60,stroke-width:2px
    
    class CHAT,EXPLORE userBox
    class AI,SMART coreBox
    class CACHE dataBox
    class NPS,WEATHER,MAPS,REVIEWS sourceBox
```

### Executive Summary

```mermaid
flowchart TB
    subgraph VALUE["🎯 Value Proposition"]
        V1["Plan outdoor adventures with AI assistance"]
        V2["Real-time weather and safety alerts"]
        V3["Personalized trail recommendations"]
        V4["Comprehensive park information"]
    end
    
    subgraph TECH["🔧 Technology Enablers"]
        T1["Google Gemini AI"]
        T2["National Park Service API"]
        T3["Live Weather Data"]
        T4["Community Reviews"]
    end
    
    subgraph OUTCOME["✅ User Outcomes"]
        O1["Safer outdoor experiences"]
        O2["Better trip planning"]
        O3["Discover new trails & spots"]
        O4["Real-time condition updates"]
    end
    
    VALUE --> TECH --> OUTCOME
    
    classDef valueStyle fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    classDef techStyle fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef outcomeStyle fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    
    class V1,V2,V3,V4 valueStyle
    class T1,T2,T3,T4 techStyle
    class O1,O2,O3,O4 outcomeStyle
```

---

## 3. Data Flow Diagram

This diagram illustrates how data moves through the system from external sources to the user interface.

```mermaid
sequenceDiagram
    participant User
    participant UI as Streamlit UI
    participant Orch as Orchestrator
    participant LLM as Gemini AI
    participant Cache as Data Cache
    participant APIs as External APIs
    
    User->>UI: Ask: "Best trails in Zion?"
    UI->>Orch: OrchestratorRequest
    
    Orch->>LLM: Parse user intent
    LLM-->>Orch: LLMParsedIntent (park=zion, type=trails)
    
    Orch->>Cache: Check for cached data
    
    alt Data exists in cache
        Cache-->>Orch: Return cached trails, weather, alerts
    else Cache miss
        Orch->>APIs: Fetch from NPS, Weather APIs
        APIs-->>Orch: Raw API responses
        Orch->>Cache: Store for future use
    end
    
    Orch->>Orch: Apply user preferences & safety filters
    Orch->>LLM: Generate response with context
    LLM-->>Orch: AI-generated recommendation
    
    Orch-->>UI: OrchestratorResponse
    UI-->>User: Display trails with reviews & conditions
```

---

## 4. Component Interaction Diagram

Shows how major components interact during typical user flows.

```mermaid
flowchart TB
    subgraph CHAT_FLOW["Chat Flow (AI Park Ranger)"]
        C1["User Query"] --> C2["Intent Parsing<br/>(Gemini)"]
        C2 --> C3["Data Aggregation"]
        C3 --> C4["Constraint Filtering"]
        C4 --> C5["Response Generation<br/>(Gemini)"]
        C5 --> C6["Display to User"]
    end
    
    subgraph EXPLORER_FLOW["Explorer Flow (Park Browser)"]
        E1["Select Park"] --> E2["Check Data Availability"]
        E2 --> E3{"Data Complete?"}
        E3 -->|Yes| E4["Load from Cache"]
        E3 -->|No| E5["Fetch & Store Data"]
        E5 --> E4
        E4 --> E6["Render UI Cards"]
    end
    
    subgraph DATA_SOURCES["Data Sources"]
        DS1["NPS API"]
        DS2["Weather API"]
        DS3["Serper Maps"]
        DS4["Firecrawl<br/>(Reviews)"]
    end
    
    C3 --> DATA_SOURCES
    E5 --> DATA_SOURCES
    
    classDef flowStep fill:#e1f5fe,stroke:#0288d1
    classDef decision fill:#fff9c4,stroke:#f9a825
    classDef source fill:#f3e5f5,stroke:#7b1fa2
    
    class C1,C2,C3,C4,C5,C6,E1,E2,E4,E5,E6 flowStep
    class E3 decision
    class DS1,DS2,DS3,DS4 source
```

---

## Quick Reference: Key Files

| Category | File | Purpose |
|----------|------|---------|
| Entry Point | `main.py` | Streamlit app, routing, session management |
| AI Core | `services/llm_service.py` | Gemini integration, prompts, response generation |
| Orchestration | `orchestrator.py` | Request handling, service coordination |
| Data Models | `models.py` | Pydantic schemas (25+ models) |
| Clients | `clients/*.py` | NPS, Weather, Serper API communication |
| Adapters | `adapters/*.py` | Raw API → Domain model transformation |
| Storage | `services/data_manager.py` | File-based caching and persistence |
| Config | `config.py` | Supported parks, UI settings |

---

*Generated on: 2026-01-19*
