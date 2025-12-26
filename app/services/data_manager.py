import os
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class DataManager:
    """
    Manages persistence of static park data (amenities, etc.) to the filesystem.
    Serves as the 'Read-Only Database' for the application at runtime.
    """
    def __init__(self, base_dir: str = "data_samples/ui_fixtures"):
        self.base_dir = base_dir

    def _get_park_dir(self, park_code: str) -> str:
        return os.path.join(self.base_dir, park_code.upper())

    def _get_amenity_filepath(self, park_code: str, entrance_name: str) -> str:
        safe_name = entrance_name.replace(" ", "_").lower()
        # Remove any non-alphanumeric chars for safety if needed
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
        filename = f"amenities_{safe_name}.json"
        return os.path.join(self._get_park_dir(park_code), filename)

    def load_amenities(self, park_code: str, entrance_name: str) -> Dict[str, List[Any]]:
        """
        Loads pre-fetched amenity data for a specific entrance.
        Returns Dict keyed by query category (e.g., 'gas station...').
        """
        filepath = self._get_amenity_filepath(park_code, entrance_name)
        
        if not os.path.exists(filepath):
            logger.debug(f"Cache MISS: {filepath}")
            return {}
            
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load cache {filepath}: {e}")
            return {}

    def save_amenities(self, park_code: str, entrance_name: str, data: Dict[str, List[Any]]):
        """
        Saves amenity data to disk. Used by Admin Tools/Pre-fetch scripts.
        """
        filepath = self._get_amenity_filepath(park_code, entrance_name)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved cache: {filepath}")
        except Exception as e:
            logger.error(f"Failed to write cache {filepath}: {e}")
