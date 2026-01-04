import logging

# --- Logging Configuration ---
def configure_logging():
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger("outdoor_concierge")

logger = configure_logging()

# --- App Configuration ---

SUPPORTED_PARKS = {
    "yose": "Yosemite National Park",
    "zion": "Zion National Park",
    "grca": "Grand Canyon National Park"
}

# Mapping for Deep Linking (?view=...)
VIEW_PARAM_MAP = {
    "trails": "Trails Browser",
    "photos": "Photo Spots",
    "camping": "Park Essentials",
    "activities": "Activities & Events",
    "webcams": "Webcams"
}

# Explorer View Options
EXPLORER_VIEW_OPTIONS = [
    "Park Essentials", 
    "Trails Browser", 
    "Photo Spots", 
    "Activities & Events", 
    "Webcams"
]

DEFAULT_PARK = "yose"
DEFAULT_VIEW = "Park Essentials"
