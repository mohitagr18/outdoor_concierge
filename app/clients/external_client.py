import os
import logging
import json
from typing import List, Dict, Any, Union

from app.clients.base_client import BaseClient
from app.models import Amenity
from app.adapters.external_adapter import parse_serper_amenities

logger = logging.getLogger(__name__)

class ExternalClient(BaseClient):
    """
    Client for External APIs (Serper, etc.).
    """
    def __init__(self, serper_key: str = None):
        self.serper_key = serper_key or os.getenv("SERPER_API_KEY")
        if not self.serper_key:
            logger.warning("SERPER_API_KEY is not set. Amenities will fail.")
        
        super().__init__(base_url="https://google.serper.dev")

    def search_maps(self, query: str, lat: float, lon: float, zoom: str = "11z") -> List[Amenity]:
        """
        Queries the Serper Maps endpoint using the 'll' parameter (@lat,lon,zoom).
        """
        if not self.serper_key:
            return []

        headers = {
            "X-API-KEY": self.serper_key,
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}/maps"

        try:
            # Construct 'll' parameter with 4 decimal precision
            # Format: @37.4535,-113.2254,11z
            ll_param = f"@{round(lat, 4)},{round(lon, 4)},{zoom}"
            
            payload = {
                "q": query,
                "ll": ll_param,
                "num": 20
            }
            
            # logger.info(f"Serper Maps Request: {payload}")

            response = self.session.post(url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Use existing adapter (maps endpoint returns 'places' array similar to places endpoint)
            return parse_serper_amenities(data)
            
        except Exception as e:
            logger.error(f"Failed to fetch maps amenities for '{query}': {e}")
            return []

    def get_amenities(self, query: Union[str, List[str]], location_lat: float, location_lon: float) -> List[Amenity]:
        """
        Legacy/Default wrapper. Iterates if query is a list.
        Defaults to 11z for general amenity searches.
        """
        queries = [query] if isinstance(query, str) else query
        combined = []
        for q in queries:
            combined.extend(self.search_maps(q, location_lat, location_lon, "11z"))
        return combined
