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
    "acad": "Acadia National Park",
    "arch": "Arches National Park",
    "badl": "Badlands National Park",
    "bibe": "Big Bend National Park",
    "bisc": "Biscayne National Park",
    "blca": "Black Canyon of the Gunnison National Park",
    "brca": "Bryce Canyon National Park",  # ✅ Full data support
    "cany": "Canyonlands National Park",
    "care": "Capitol Reef National Park",
    "cave": "Carlsbad Caverns National Park",
    "chis": "Channel Islands National Park",
    "cong": "Congaree National Park",
    "crla": "Crater Lake National Park",
    "cuva": "Cuyahoga Valley National Park",
    "deva": "Death Valley National Park",
    "dena": "Denali National Park",
    "drto": "Dry Tortugas National Park",
    "ever": "Everglades National Park",
    "gaar": "Gates of the Arctic National Park",
    "jeff": "Gateway Arch National Park",
    "glac": "Glacier National Park",
    "glba": "Glacier Bay National Park",
    "grca": "Grand Canyon National Park",  # ✅ Full data support
    "grte": "Grand Teton National Park",
    "grba": "Great Basin National Park",
    "grsm": "Great Smoky Mountains National Park",
    "gumo": "Guadalupe Mountains National Park",
    "hale": "Haleakalā National Park",
    "havo": "Hawaiʻi Volcanoes National Park",
    "hosp": "Hot Springs National Park",
    "indu": "Indiana Dunes National Park",
    "isro": "Isle Royale National Park",
    "jotr": "Joshua Tree National Park",
    "katm": "Katmai National Park",
    "kefj": "Kenai Fjords National Park",
    "kova": "Kobuk Valley National Park",
    "lacl": "Lake Clark National Park",
    "lavo": "Lassen Volcanic National Park",
    "maca": "Mammoth Cave National Park",
    "meve": "Mesa Verde National Park",
    "mora": "Mount Rainier National Park",
    "neri": "New River Gorge National Park",
    "noca": "North Cascades National Park",
    "olym": "Olympic National Park",
    "pefo": "Petrified Forest National Park",
    "pinn": "Pinnacles National Park",
    "redw": "Redwood National Park",
    "romo": "Rocky Mountain National Park",
    "sagu": "Saguaro National Park",
    "seki": "Sequoia & Kings Canyon National Parks",
    "shen": "Shenandoah National Park",
    "thro": "Theodore Roosevelt National Park",
    "viis": "Virgin Islands National Park",
    "voya": "Voyageurs National Park",
    "whsa": "White Sands National Park",
    "wica": "Wind Cave National Park",
    "wrst": "Wrangell-St. Elias National Park",
    "yell": "Yellowstone National Park",
    "yose": "Yosemite National Park",  # ✅ Full data support
    "zion": "Zion National Park",  # ✅ Full data support
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
