import os
import sys
import logging
from typing import List

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.clients.nps_client import NPSClient
from app.clients.weather_client import WeatherClient
from app.engine.constraints import ConstraintEngine, UserPreference
from app.models import TrailSummary
from dotenv import load_dotenv

load_dotenv()   

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Phase 2 Verification...")

    # 1. Initialize Clients
    nps_key = os.getenv("NPS_API_KEY")
    weather_key = os.getenv("WEATHER_API_KEY")
    
    if not nps_key or not weather_key:
        logger.error("Missing API Keys! Please set NPS_API_KEY and WEATHER_API_KEY in .env")
        return

    nps_client = NPSClient(api_key=nps_key)
    weather_client = WeatherClient(api_key=weather_key)
    engine = ConstraintEngine()

    # 2. Select Park
    PARK_CODE = "yose"
    logger.info(f"Target Park: {PARK_CODE}")

    # 3. Fetch Data (Live)
    logger.info("Fetching Live Data...")
    park = nps_client.get_park_details(PARK_CODE)
    alerts = nps_client.get_alerts(PARK_CODE)
    
    # Fetch weather using park location
    if park and park.location:
        weather = weather_client.get_forecast(PARK_CODE, park.location.lat, park.location.lon)
    else:
        logger.warning("Could not fetch park location, skipping weather.")
        weather = None

    # 4. Mock Trails (Since scraping is slow/complex for this quick test)
    logger.info("Loading Mock Trails...")
    trails = [
        TrailSummary(
            name="Mist Trail", difficulty="hard", length_miles=6.0, elevation_gain_ft=2000, 
            route_type="out and back", average_rating=4.8, total_reviews=5000, 
            description="Famous waterfall hike.", features=["scenic", "no dogs"], surface_types=["rocky"]
        ),
        TrailSummary(
            name="Lower Yosemite Fall", difficulty="easy", length_miles=1.2, elevation_gain_ft=50, 
            route_type="loop", average_rating=4.6, total_reviews=3000, 
            description="Easy walk to waterfall.", features=["dogs on leash", "kid friendly"], surface_types=["paved"]
        )
    ]

    # 5. Define User Preferences
    user_prefs = UserPreference(
        max_difficulty="moderate", # Should filter out Mist Trail
        dog_friendly=True,         # Should filter out Mist Trail (double filter)
        min_rating=4.0
    )
    logger.info(f"User Preferences: {user_prefs}")

    # 6. Run Constraint Engine
    logger.info("Running Constraint Engine...")
    
    # A. Safety Check
    safety = engine.analyze_safety(weather, alerts)
    logger.info(f"Safety Status: {safety.status}")
    for reason in safety.reason:
        logger.info(f"  - {reason}")

    # B. Trail Filtering
    vetted_trails = engine.filter_trails(trails, user_prefs)
    
    # 7. Output Results
    print("\n" + "="*40)
    print(f"🌲 OUTDOOR ADVENTURE CONCIERGE REPORT")
    print(f"🌲 Park: {park.fullName if park else PARK_CODE}")
    print("="*40)
    
    print(f"\n🚦 Safety Status: {safety.status.upper()}")
    if safety.reason:
        print("⚠️  Alerts:")
        for r in safety.reason:
            print(f"   - {r}")

    print(f"\n🥾 Recommended Trails ({len(vetted_trails)} found):")
    if not vetted_trails:
        print("   No trails matched your criteria.")
    else:
        for t in vetted_trails:
            print(f"   - {t.name} ({t.difficulty}, {t.length_miles} mi)")
            print(f"     Rating: {t.average_rating} | Features: {', '.join(t.features)}")

    print("\n✅ Verification Complete.")

if __name__ == "__main__":
    main()
