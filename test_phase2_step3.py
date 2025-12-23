import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import unittest
from app.engine.constraints import ConstraintEngine, UserPreference, SafetyStatus
from app.models import TrailSummary, WeatherSummary, Alert, DailyForecast

class TestConstraintEngine(unittest.TestCase):

    def setUp(self):
        self.engine = ConstraintEngine()
        
        # Mock Trails
        self.trail_easy = TrailSummary(
            name="Easy Walk", difficulty="easy", length_miles=2.0, elevation_gain_ft=100, 
            route_type="loop", average_rating=4.5, total_reviews=100, description="Nice", 
            features=["dogs on leash", "kid friendly"], surface_types=["paved"]
        )
        self.trail_hard = TrailSummary(
            name="Hard Climb", difficulty="hard", length_miles=10.0, elevation_gain_ft=3000, 
            route_type="out and back", average_rating=4.8, total_reviews=50, description="Tough", 
            features=["no dogs"], surface_types=["rocky"]
        )

    def test_filter_trails_difficulty(self):
        # Expecting ONLY the easy trail
        prefs = UserPreference(max_difficulty="easy")
        results = self.engine.filter_trails([self.trail_easy, self.trail_hard], prefs)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Easy Walk")

    def test_filter_trails_dogs(self):
        # Expecting ONLY the dog friendly trail
        prefs = UserPreference(dog_friendly=True)
        results = self.engine.filter_trails([self.trail_easy, self.trail_hard], prefs)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Easy Walk")

    def test_safety_check_heat(self):
        # Input 105F. Code Threshold > 100F. Result should be No-Go.
        weather = WeatherSummary(
            parkCode="yose", current_temp_f=111.0, current_condition="Sunny", 
            forecast=[], weather_alerts=[]
        )
        status = self.engine.analyze_safety(weather, [])
        self.assertEqual(status.status, "No-Go")
        self.assertIn("Extreme heat", status.reason[0])

    def test_safety_check_alerts(self):
        alert = Alert(
            id="1", parkCode="yose", title="Park Closed due to Fire", 
            description="...", category="Danger", lastIndexedDate="2023"
        )
        status = self.engine.analyze_safety(None, [alert])
        self.assertEqual(status.status, "No-Go")
        self.assertIn("Critical Alert", status.reason[0])

if __name__ == "__main__":
    unittest.main()
