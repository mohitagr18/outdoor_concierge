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
from app.ui.views.park_explorer_amenities import render_amenities_dashboard
from app.ui.views.park_explorer_trails import render_trails_browser
from app.ui.views.park_explorer_photos import render_photo_spots

# --- Page Configuration ---
st.set_page_config(
    page_title="Outdoor Adventure Concierge",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    
    # Top-level Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trails", len(static_data.get("trails", [])))
    c2.metric("Photo Spots", len(static_data.get("photo_spots", [])))
    c3.metric("Active Alerts", len(volatile_data.get("alerts", [])), delta="Live")
    c4.metric("Campgrounds", len(static_data.get("campgrounds", [])))
    
    st.divider()
    
    # Sub-Navigation for Explorer Views
    view_mode = st.radio(
        "Explore Mode", 
        ["Services & Amenities", "Trails Browser", "Photo Spots"],
        horizontal=True,
        label_visibility="collapsed"
    )

    if view_mode == "Services & Amenities":
        render_amenities_dashboard(park_code, orchestrator)
    
    elif view_mode == "Trails Browser":
        render_trails_browser(park_code, static_data)
        
    elif view_mode == "Photo Spots":
        render_photo_spots(static_data.get("photo_spots", []))
