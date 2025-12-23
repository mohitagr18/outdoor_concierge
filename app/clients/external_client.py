import os
import logging
import json
from typing import List

from app.clients.base_client import BaseClient
from app.models import Amenity
from app.adapters.external_adapter import parse_serper_amenities

logger = logging.getLogger(__name__)

class ExternalClient(BaseClient):
    """
    Client for External APIs (Serper, etc.).
    """
    
    def __init__(self, serper_key: os.getenv("SERPER_API_KEY") = None):
        self.serper_key = serper_key or os.getenv("SERPER_API_KEY")
        if not self.serper_key:
            # We log a warning but don't crash, as this might be optional for some tests
            logger.warning("SERPER_API_KEY is not set. Amenities will fail.")
            
        # Base URL for Serper
        super().__init__(base_url="https://google.serper.dev")

    def get_amenities(self, query: str, location_lat: float, location_lon: float) -> List[Amenity]:
        """
        Search for amenities near a location using Serper.
        Query example: "gas stations near Yosemite Valley"
        """
        if not self.serper_key:
            return []

        payload = {
            "q": query,
            "location": f"{location_lat},{location_lon}", # Serper logic might vary, usually it takes a text 'location' or lat/lon in specific format.
            # Serper 'places' endpoint is best for this.
        }
        
        headers = {
            "X-API-KEY": self.serper_key,
            "Content-Type": "application/json"
        }

        try:
            # Serper uses POST for detailed queries usually, but BASE_CLIENT is designed for GET.
            # We will override or use requests directly if BaseClient is too strict.
            # Actually, Serper 'search' is POST.
            
            url = f"{self.base_url}/places"
            response = self.session.post(url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            return parse_serper_amenities(data)
            
        except Exception as e:
            logger.error(f"Failed to fetch amenities for '{query}': {e}")
            return []
