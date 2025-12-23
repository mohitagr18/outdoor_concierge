import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import MagicMock, patch
from app.clients.weather_client import WeatherClient
from app.clients.external_client import ExternalClient
from app.models import WeatherSummary, Amenity

class TestStep2Clients(unittest.TestCase):

    def setUp(self):
        os.environ["WEATHER_API_KEY"] = "TEST_WEATHER"
        os.environ["SERPER_API_KEY"] = "TEST_SERPER"
        self.weather_client = WeatherClient()
        self.ext_client = ExternalClient()

    @patch("app.clients.base_client.requests.Session.get")
    def test_get_forecast(self, mock_get):
        # Mock Weather Response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "current": {"temp_f": 65.0, "condition": {"text": "Sunny"}},
            "forecast": {"forecastday": []}
        }
        mock_get.return_value = mock_response

        result = self.weather_client.get_forecast("yose", 37.8, -119.5)
        self.assertIsInstance(result, WeatherSummary)
        self.assertEqual(result.current_temp_f, 65.0)

    @patch("app.clients.base_client.requests.Session.post")
    def test_get_amenities(self, mock_post):
        # Mock Serper Response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "places": [{
                "title": "Shell Gas",
                "category": "Gas Station",
                "address": "123 Main St",
                "rating": 4.5,
                "cid": "12345"
            }]
        }
        mock_post.return_value = mock_response

        result = self.ext_client.get_amenities("gas", 37.8, -119.5)
        self.assertIsInstance(result, list)
        if result:
            self.assertIsInstance(result[0], Amenity)
            self.assertEqual(result[0].name, "Shell Gas")

if __name__ == "__main__":
    unittest.main()
