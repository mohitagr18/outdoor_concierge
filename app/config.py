import logging

# --- Logging Configuration ---
def configure_logging():
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger("outdoor_concierge")

logger = configure_logging()

# --- App Configuration ---

# All US National Parks (alphabetically by park name)
# Parks with full data support are marked with comments
SUPPORTED_PARKS = {
    "brca": "Bryce Canyon National Park",  # ✅ Full data support
    "glac": "Glacier National Park",       # ✅ Full data support
    "grsm": "Great Smoky Mountains National Park", # ✅ Full data support
    "yose": "Yosemite National Park",      # ✅ Full data support
    "zion": "Zion National Park",          # ✅ Full data support
}

# Mapping for Deep Linking (?view=...)
VIEW_PARAM_MAP = {
    "trails": "Trails Browser",
    "photos": "Photo Spots",
    "drives": "Scenic Drives",
    "camping": "Park Essentials",
    "activities": "Activities & Events",
    "webcams": "Webcams"
}

# Explorer View Options
EXPLORER_VIEW_OPTIONS = [
    "Park Essentials", 
    "Trails Browser", 
    "Photo Spots",
    "Scenic Drives",
    "Activities & Events", 
    "Webcams"
]

DEFAULT_PARK = "yose"
DEFAULT_VIEW = "Park Essentials"
