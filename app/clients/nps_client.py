import os
import logging
from typing import List, Optional

from app.clients.base_client import BaseClient
from app.models import (
    ParkContext, Alert, Event, Campground, VisitorCenter, 
    Webcam, Place, ThingToDo, PassportStamp
)
from app.adapters.nps_adapter import (
    parse_nps_park, parse_nps_alerts, parse_nps_events,
    parse_nps_campgrounds, parse_nps_visitor_centers,
    parse_nps_webcams, parse_nps_places,
    parse_nps_things_to_do, parse_nps_passport_stamps
)

logger = logging.getLogger(__name__)

class NPSClient(BaseClient):
    """
    Client for the National Park Service (NPS) API.
    Fetch park details, alerts, events, and extended amenities.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        # Use env var if not passed explicitly
        self.api_key = api_key or os.getenv("NPS_API_KEY")
        if not self.api_key:
            raise ValueError("NPS_API_KEY is not set. Please provide it or set it in the environment.")
            
        super().__init__(base_url="https://developer.nps.gov/api/v1")
        
    def _get_headers(self):
        return {"X-Api-Key": self.api_key}

    def get_park_details(self, park_code: str) -> Optional[ParkContext]:
        """
        Fetch core details for a specific park.
        NOTE: This does NOT automatically fetch children (campgrounds, etc.) 
        to save API calls. You must call specific methods to populate them.
        """
        params = {"parkCode": park_code, "limit": 1}
        try:
            data = self._get("parks", params=params, headers=self._get_headers())
            items = data.get("data", [])
            if not items:
                logger.warning(f"No park found for code: {park_code}")
                return None
            return parse_nps_park(items[0])
        except Exception as e:
            logger.error(f"Failed to fetch park details for {park_code}: {e}")
            return None

    def get_alerts(self, park_code: str, limit: int = 50) -> List[Alert]:
        try:
            params = {"parkCode": park_code, "limit": limit}
            data = self._get("alerts", params=params, headers=self._get_headers())
            return parse_nps_alerts(data)
        except Exception as e:
            logger.error(f"Failed to fetch alerts for {park_code}: {e}")
            return []

    def get_events(self, park_code: str, limit: int = 50) -> List[Event]:
        try:
            params = {"parkCode": park_code, "limit": limit}
            data = self._get("events", params=params, headers=self._get_headers())
            return parse_nps_events(data)
        except Exception as e:
            logger.error(f"Failed to fetch events for {park_code}: {e}")
            return []

    def get_campgrounds(self, park_code: str, limit: int = 50) -> List[Campground]:
        try:
            params = {"parkCode": park_code, "limit": limit}
            data = self._get("campgrounds", params=params, headers=self._get_headers())
            return parse_nps_campgrounds(data)
        except Exception as e:
            logger.error(f"Failed to fetch campgrounds for {park_code}: {e}")
            return []

    def get_visitor_centers(self, park_code: str, limit: int = 50) -> List[VisitorCenter]:
        try:
            params = {"parkCode": park_code, "limit": limit}
            data = self._get("visitorcenters", params=params, headers=self._get_headers())
            return parse_nps_visitor_centers(data)
        except Exception as e:
            logger.error(f"Failed to fetch visitor centers for {park_code}: {e}")
            return []

    def get_webcams(self, park_code: str, limit: int = 50) -> List[Webcam]:
        try:
            params = {"parkCode": park_code, "limit": limit}
            data = self._get("webcams", params=params, headers=self._get_headers())
            return parse_nps_webcams(data)
        except Exception as e:
            logger.error(f"Failed to fetch webcams for {park_code}: {e}")
            return []

    def get_places(self, park_code: str, limit: int = 500) -> List[Place]:
        try:
            params = {"parkCode": park_code, "limit": limit}
            data = self._get("places", params=params, headers=self._get_headers())
            return parse_nps_places(data)
        except Exception as e:
            logger.error(f"Failed to fetch places for {park_code}: {e}")
            return []

    def get_things_to_do(self, park_code: str, limit: int = 500) -> List[ThingToDo]:
        try:
            params = {"parkCode": park_code, "limit": limit}
            data = self._get("thingstodo", params=params, headers=self._get_headers())
            return parse_nps_things_to_do(data)
        except Exception as e:
            logger.error(f"Failed to fetch things to do for {park_code}: {e}")
            return []

    def get_passport_stamps(self, park_code: str, limit: int = 50) -> List[PassportStamp]:
        try:
            params = {"parkCode": park_code, "limit": limit}
            data = self._get("passportstamplocations", params=params, headers=self._get_headers())
            return parse_nps_passport_stamps(data)
        except Exception as e:
            logger.error(f"Failed to fetch passport stamps for {park_code}: {e}")
            return []

    def get_full_park_data(self, park_code: str) -> Optional[ParkContext]:
        """
        Orchestrator method to fetch EVERYTHING for a single park.
        Returns a populated ParkContext with all children.
        """
        park = self.get_park_details(park_code)
        if not park:
            return None

        # Parallel fetching would be better here in production, 
        # but sequential is safer for now to avoid rate limits.
        park.campgrounds = self.get_campgrounds(park_code)
        park.visitor_centers = self.get_visitor_centers(park_code)
        park.webcams = self.get_webcams(park_code)
        park.places = self.get_places(park_code)
        park.things_to_do = self.get_things_to_do(park_code)
        park.passport_stamps = self.get_passport_stamps(park_code)
        
        return park
