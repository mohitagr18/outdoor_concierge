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
# App imports
from app.orchestrator import OutdoorConciergeOrchestrator, SessionContext
from app.clients.nps_client import NPSClient
from app.clients.weather_client import WeatherClient
from app.clients.external_client import ExternalClient
from app.services.llm_service import GeminiLLMService
from app.ui.data_access import get_park_static_data, get_volatile_data, clear_volatile_cache

# Config & Styles
from app.config import (
    SUPPORTED_PARKS, VIEW_PARAM_MAP, EXPLORER_VIEW_OPTIONS, 
    DEFAULT_PARK, DEFAULT_VIEW, logger
)
from app.ui.styles import inject_global_styles, inject_radio_tab_styles

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

# Inject Global CSS
inject_global_styles()

# --- 1. Session State Initialization ---
if "session_context" not in st.session_state:
    st.session_state.session_context = SessionContext()

if "volatile_cache" not in st.session_state:
    st.session_state.volatile_cache = {"weather": {}, "alerts": {}, "events": {}}

if "selected_park" not in st.session_state:
    st.session_state.selected_park = DEFAULT_PARK

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
    
    if target_view in VIEW_PARAM_MAP:
        st.session_state.explorer_view = VIEW_PARAM_MAP[target_view]
        
        # Special Handling for "Campgrounds" toggle
        if target_view == "camping":
            st.session_state.essentials_toggle = "In-Park Services"
    
    # Clear params to prevent persistent state
    st.query_params.clear()
    
# --- 3. Sidebar ---
with st.sidebar:
    st.title("🌲 Adventure Concierge")
    
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
    
    # Sub-Navigation for Explorer Views
    
    # 1. Initialize View State
    if "explorer_view" not in st.session_state:
        st.session_state.explorer_view = DEFAULT_VIEW

    # 3. Custom CSS for "Radio Tabs"
    inject_radio_tab_styles()

    view_options = EXPLORER_VIEW_OPTIONS
    
    # Ensure valid state
    if st.session_state.explorer_view not in view_options:
        st.session_state.explorer_view = DEFAULT_VIEW

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
