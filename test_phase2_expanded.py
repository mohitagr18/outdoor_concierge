import os
import unittest
from unittest.mock import MagicMock, patch
from app.clients.nps_client import NPSClient
from app.models import ParkContext, Campground, Webcam

class TestNPSClientExpanded(unittest.TestCase):

    def setUp(self):
        os.environ["NPS_API_KEY"] = "TEST_KEY"
        self.client = NPSClient()

    @patch("app.clients.base_client.requests.Session.get")
    def test_get_campgrounds(self, mock_get):
        # Mock Response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{
                "id": "camp1",
                "name": "Lower Pines",
                "description": "Near the river.",
                "campsites": {"totalSites": "50", "tentOnly": "10"}
            }]
        }
        mock_get.return_value = mock_response

        # Call
        result = self.client.get_campgrounds("yose")

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], Campground)
        self.assertEqual(result[0].name, "Lower Pines")
        self.assertEqual(result[0].campsites["totalSites"], "50")

    @patch("app.clients.base_client.requests.Session.get")
    def test_get_webcams(self, mock_get):
        # Mock Response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{
                "id": "web1",
                "title": "Half Dome Cam",
                "description": "View of Half Dome",
                "isStreaming": True,
                "relatedParks": [{"parkCode": "yose"}]
            }]
        }
        mock_get.return_value = mock_response

        # Call
        result = self.client.get_webcams("yose")

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], Webcam)
        self.assertTrue(result[0].isStreaming)

if __name__ == "__main__":
    unittest.main()
