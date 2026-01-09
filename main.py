import streamlit as st
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables (force override to respect .env file changes)
load_dotenv(override=True)

# App imports
# App imports
from app.orchestrator import OutdoorConciergeOrchestrator, SessionContext
from app.clients.nps_client import NPSClient
from app.clients.weather_client import WeatherClient
from app.clients.external_client import ExternalClient
from app.services.llm_service import GeminiLLMService
from app.services.park_data_fetcher import ParkDataFetcher
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
    # Empty spacer to keep sidebar visible with background image
    st.markdown("<div style='height: 100vh;'></div>", unsafe_allow_html=True)

# --- 4. Load Data ---
park_code = st.session_state.selected_park
nps_client = orchestrator.nps if orchestrator else None
static_data = get_park_static_data(park_code, nps_client=nps_client)
volatile_data = get_volatile_data(park_code, orchestrator) if orchestrator else {}

# --- 5. Main Tabs ---
st.markdown("""
    <h1 style="margin-bottom: 0.25rem;">⛰️ Adventure Concierge</h1>
    <p style="font-size: 1.25rem; color: #666; margin-bottom: 1.5rem;">
        Your AI-powered guide for park planning, trail discovery, and real-time conditions.
    </p>
    """, unsafe_allow_html=True)

tab_chat, tab_explorer = st.tabs(["🤠 AI Park Ranger", "🔭 Park Explorer"])

with tab_chat:

    
    # Initialize history if empty (handled by SessionContext, but we need UI display list)
    if "ui_chat_history" not in st.session_state:
        st.session_state.ui_chat_history = []
        # Add welcome message
        st.session_state.ui_chat_history.append({"role": "assistant", "content": "Hello! I can help you plan your trip, find hikes, or check safety conditions. What's on your mind?"})

    # Display Chat History
    for msg in st.session_state.ui_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    # Handle Input
    if prompt := st.chat_input("Ask about reviews, hikes, or safety..."):
        # 1. Display User Message
        st.session_state.ui_chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Call Orchestrator
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Construct Request
                    # context is already in st.session_state.session_context
                    from app.orchestrator import OrchestratorRequest
                    
                    req = OrchestratorRequest(
                        user_query=prompt,
                        # Serialize to dict to avoid Pydantic class mismatch on reload
                        session_context=st.session_state.session_context.model_dump()
                    )
                    
                    if orchestrator:
                        resp = orchestrator.handle_query(req)
                        
                        # Update Context
                        st.session_state.session_context = resp.updated_context
                        
                        # Display Response
                        st.markdown(resp.chat_response.message, unsafe_allow_html=True) # REVERTED FROM render_chat_message
                        
                        # Append to History
                        st.session_state.ui_chat_history.append({"role": "assistant", "content": resp.chat_response.message})
                        
                        # Debug Info (Optional - expander)
                        # with st.expander("Debug: Intent & Tools"):
                        #     st.json(resp.parsed_intent.model_dump())
                        #     if resp.vetted_trails:
                        #         st.write(f"Considered {len(resp.vetted_trails)} trails")
                    else:
                        st.error("Orchestrator unavailable (check API keys).")

                except Exception as e:
                    st.error(f"Error: {e}")
                    logger.error(f"Chat Error: {e}")

with tab_explorer:
    # Park selector at top
    col_label, col_selector = st.columns([2, 2])
    with col_label:
        st.markdown("<p style='font-size: 1.4rem; margin-top: 0.5rem;'>🏞️ <strong>Choose a National Park to explore:</strong></p>", unsafe_allow_html=True)
    with col_selector:
        selected_code = st.selectbox(
            "Select Park",
            options=list(SUPPORTED_PARKS.keys()),
            format_func=lambda x: SUPPORTED_PARKS[x],
            index=list(SUPPORTED_PARKS.keys()).index(st.session_state.selected_park) if st.session_state.selected_park in SUPPORTED_PARKS else 0,
            label_visibility="collapsed"
        )
        if selected_code != st.session_state.selected_park:
            st.session_state.selected_park = selected_code
            st.session_state.session_context.current_park_code = selected_code
            st.rerun()
    
    st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
    st.header(f"Exploring {SUPPORTED_PARKS[st.session_state.selected_park]}")
    
    # Check if park has data before rendering
    fetcher = ParkDataFetcher(nps_client=orchestrator.nps if orchestrator else None)
    
    if not fetcher.has_basic_data(park_code):
        st.warning(f"⚠️ No data found for {SUPPORTED_PARKS.get(park_code, park_code)}")
        st.info("This park needs initial data setup. This involves fetching park info, trails, and more.")
        
        missing = fetcher.get_missing_fixtures(park_code)
        with st.expander("Missing Data Files"):
            for m in missing:
                st.write(f"• {m}")
        
        if st.button("🚀 Fetch Park Data", type="primary"):
            with st.spinner("Fetching data... This may take a few minutes."):
                progress = st.progress(0)
                status_text = st.empty()
                
                def update_progress(current, total, message):
                    if total > 0:
                        progress.progress(current / total)
                    status_text.text(message)
                
                try:
                    result = fetcher.ensure_park_data(
                        park_code,
                        include_trails=True,
                        include_rankings=True,
                        include_photo_spots=True,
                        include_amenities=True,
                        progress_callback=update_progress
                    )
                    
                    # Show results
                    success_count = sum(1 for v in result.get("operations", {}).values() if isinstance(v, dict) and "error" not in v)
                    total_ops = len(result.get("operations", {}))
                    
                    st.success(f"✅ Data fetched! {success_count}/{total_ops} operations successful.")
                    
                    # Show any errors
                    for op_name, op_result in result.get("operations", {}).items():
                        if isinstance(op_result, dict) and "error" in op_result:
                            st.error(f"{op_name}: {op_result['error']}")
                    
                    st.rerun()  # Reload with new data
                    
                except Exception as e:
                    st.error(f"❌ Error fetching data: {e}")
                    st.info("Please try again in a few minutes.")
        
        st.stop()  # Don't render the rest of the explorer
    
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
        render_essentials_dashboard(park_code, orchestrator, static_data, volatile_data)
        
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
