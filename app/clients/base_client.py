import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any

# Configure a module-level logger
logger = logging.getLogger(__name__)

class BaseClient:
    """
    A robust HTTP base client with built-in retry logic and timeout handling.
    """
    def __init__(self, base_url: str, timeout: int = 10, retries: int = 3):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=retries,
            backoff_factor=1,  # 1s, 2s, 4s...
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Internal method to perform GET requests safely.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err} - URL: {url}")
            # In a production app, we might raise a custom exception here
            raise 
        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f"Connection error occurred: {conn_err} - URL: {url}")
            raise
        except requests.exceptions.Timeout as timeout_err:
            logger.error(f"Timeout occurred: {timeout_err} - URL: {url}")
            raise
        except requests.exceptions.RequestException as err:
            logger.error(f"An unexpected error occurred: {err} - URL: {url}")
            raise
