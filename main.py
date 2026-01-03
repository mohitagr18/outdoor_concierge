import streamlit as st
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# App imports
from app.orchestrator import OutdoorConciergeOrchestrator, SessionContext
from app.clients.nps_client import NPSClient
from app.clients.weather_client import WeatherClient
from app.clients.external_client import ExternalClient
from app.services.llm_service import GeminiLLMService
from app.ui.data_access import get_park_static_data, get_volatile_data, clear_volatile_cache

# Import Views
from app.ui.views.park_explorer_essentials import render_essentials_dashboard
from app.ui.views.park_explorer_trails import render_trails_browser
from app.ui.views.park_explorer_photos import render_photo_spots
from app.ui.views.park_explorer_activities import render_activities_grid
from app.ui.views.park_explorer_events import render_events_list
from app.ui.views.park_explorer_webcams import render_webcams_grid

# --- Page Configuration ---
st.set_page_config(
    page_title="Outdoor Adventure Concierge",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Big Tabs ---
st.markdown("""
<style>
    /* 1. Global Tab Styling (Apply to Outer Tabs) */
    div[data-testid="stTabs"] button {
        gap: 30px; /* More space between tabs */
    }
    div[data-testid="stTabs"] button p {
        font-size: 16px !important; /* Smaller, cleaner font */
        font-weight: 500 !important;
    }
    
    /* 2. Inner Tab Styling (Removed specific marker hack, standardizing for now) */

    /* 3. Color Overrides for ALL Tabs (Remove Red) */
    /* Selected Tab Text */
    div[data-testid="stTabs"] button[aria-selected="true"] p {
        color: #2c3e50 !important; /* Dark Blue-Grey instead of Red */
    }
    /* Selected Tab Top Border */
    div[data-testid="stTabs"] button[aria-selected="true"] {
        border-top-color: #2c3e50 !important;
    }
    div[data-testid="stTabs"] button:hover {
        color: #2c3e50 !important;
        border-color: #2c3e50 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. Session State Initialization ---
if "session_context" not in st.session_state:
    st.session_state.session_context = SessionContext()

if "volatile_cache" not in st.session_state:
    st.session_state.volatile_cache = {"weather": {}, "alerts": {}, "events": {}}

if "selected_park" not in st.session_state:
    st.session_state.selected_park = "yose"

# --- 2. Service Initialization (Cached) ---
@st.cache_resource
def get_orchestrator():
    if not os.getenv("NPS_API_KEY") or not os.getenv("GEMINI_API_KEY"):
        st.error("Missing API Keys in .env")
        return None

    try:
        orchestrator = OutdoorConciergeOrchestrator(
            llm_service=GeminiLLMService(api_key=os.getenv("GEMINI_API_KEY")),
            nps_client=NPSClient(),
            weather_client=WeatherClient(),
            external_client=ExternalClient()
        )
        return orchestrator
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        return None

orchestrator = get_orchestrator()

# --- 2b. Handle Deep Linking (Query Params) ---
# Check early to redirect before rendering
if "view" in st.query_params:
    target_view = st.query_params["view"]
    view_map = {
        "trails": "Trails Browser",
        "photos": "Photo Spots",
        "camping": "Park Essentials",
        "activities": "Activities & Events",
        "webcams": "Webcams"
    }
    
    if target_view in view_map:
        st.session_state.explorer_view = view_map[target_view]
        
        # Special Handling for "Campgrounds" toggle
        if target_view == "camping":
            st.session_state.essentials_toggle = "In-Park Services"
    
    # Clear params to prevent persistent state
    st.query_params.clear()
    
# --- 3. Sidebar ---
with st.sidebar:
    st.title("🌲 Adventure Concierge")
    
    SUPPORTED_PARKS = {
        "yose": "Yosemite National Park",
        "zion": "Zion National Park",
        "grca": "Grand Canyon National Park"
    }
    
    selected_code = st.selectbox(
        "Select Park",
        options=list(SUPPORTED_PARKS.keys()),
        format_func=lambda x: SUPPORTED_PARKS[x],
        index=0 if st.session_state.selected_park not in SUPPORTED_PARKS else list(SUPPORTED_PARKS.keys()).index(st.session_state.selected_park)
    )

    if selected_code != st.session_state.selected_park:
        st.session_state.selected_park = selected_code
        st.session_state.session_context.current_park_code = selected_code
        st.rerun()

    st.divider()
    visit_date = st.date_input("Visit Date")
    
    if st.button("🔄 Refresh Live Data"):
        clear_volatile_cache()
        st.rerun()
    
    st.info(f"Active Context: **{selected_code.upper()}**")

# --- 4. Load Data ---
park_code = st.session_state.selected_park
static_data = get_park_static_data(park_code)
volatile_data = get_volatile_data(park_code, orchestrator) if orchestrator else {}

# --- 5. Main Tabs ---
tab_chat, tab_explorer = st.tabs(["💬 Concierge Chat", "🗺️ Park Explorer"])

with tab_chat:
    st.header("Concierge Chat")
    st.write("Interact with the AI to plan your trip.")
    # (Chat implementation coming in Step 7)
    prompt = st.chat_input("Ask about the park...")
    if prompt:
        st.write(f"User sent: {prompt}")

with tab_explorer:
    st.header(f"Exploring {SUPPORTED_PARKS[st.session_state.selected_park]}")
    
    # # Top-level Metrics
    # c1, c2, c3, c4 = st.columns(4)
    # c1.metric("Trails", len(static_data.get("trails", [])))
    # c2.metric("Photo Spots", len(static_data.get("photo_spots", [])))
    # c3.metric("Active Alerts", len(volatile_data.get("alerts", [])), delta="Live")
    # c4.metric("Campgrounds", len(static_data.get("campgrounds", [])))
    
    # st.divider()
    
    # Sub-Navigation for Explorer Views
    
    # 1. Initialize View State
    if "explorer_view" not in st.session_state:
        st.session_state.explorer_view = "Park Essentials"

    # 3. Custom CSS for "Radio Tabs"
    st.markdown("""
    <style>
        /* Hide the default radio circles */
        div[data-testid="stRadio"] > label > div:first-child {
            display: none;
        }
        div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
            display: none;
        }
        
        /* Container styling */
        div[data-testid="stRadio"] > div[role="radiogroup"] {
            gap: 12px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 0px;
        }

        /* Tab styling */
        div[data-testid="stRadio"] > div[role="radiogroup"] > label {
            background-color: transparent;
            padding: 8px 16px;
            border-radius: 8px 8px 0 0;
            border: 1px solid transparent; 
            margin-bottom: -1px;
            transition: all 0.2s;
        }
        
        /* Hover */
        div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
            background-color: #f1f5f9;
            color: #0f172a;
        }
        
        /* Selected Tab Styling */
        div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
            background-color: #f1f5f9;
            border-bottom: 2px solid #2c3e50;
            color: #2c3e50;
        }
        
        div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p {
            color: #2c3e50 !important;
            font-weight: 700;
        }
    </style>
    """, unsafe_allow_html=True)

    view_options = [
        "Park Essentials", "Trails Browser", "Photo Spots", "Activities & Events", "Webcams"
    ]
    
    # Ensure valid state
    if st.session_state.explorer_view not in view_options:
        st.session_state.explorer_view = "Park Essentials"

    selected_view = st.radio(
        "Explorer View",
        options=view_options,
        horizontal=True,
        label_visibility="collapsed",
        key="explorer_view"
    )
    
    # st.divider()

    # 4. Render Views
    if selected_view == "Park Essentials":
        render_essentials_dashboard(park_code, orchestrator, static_data)
        
    elif selected_view == "Trails Browser":
        render_trails_browser(park_code, static_data)
        
    elif selected_view == "Photo Spots":
        render_photo_spots(static_data.get("photo_spots", []))

    elif selected_view == "Activities & Events":
        # Internal sub-navigation using Radio Buttons
        activity_view = st.radio(
            "Select View",
            options=["Things to Do", "Upcoming Events"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        st.write("") # Spacer
        
        if activity_view == "Things to Do":
            render_activities_grid(static_data.get("things_to_do", []))
            
        elif activity_view == "Upcoming Events":
            render_events_list(
                volatile_data.get("events", []),
                visit_date=visit_date
            )

    elif selected_view == "Webcams":
        render_webcams_grid(static_data.get("webcams", []))
