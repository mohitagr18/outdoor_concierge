import os
import json
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
NPS_DATA_ROOT = PROJECT_ROOT / "data_samples" / "ui_fixtures"

WEATHER_BASE_URL = "https://api.weatherapi.com/v1/forecast.json"


def load_weather_key() -> str:
    load_dotenv(ENV_PATH)
    key = os.getenv("WEATHER_API_KEY")
    if not key:
        raise RuntimeError("WEATHER_API_KEY is not set in .env")
    return key


def load_park_lat_lon(park_dir: Path) -> Dict[str, float]:
    parks_path = park_dir / "park_details.json"
    with parks_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # UI Fixture style uses 'location' key from ParkContext
    loc = data.get("location")
    if not loc or "lat" not in loc or "lon" not in loc:
        raise RuntimeError(f"No valid location data in {parks_path}")

    return {"lat": float(loc["lat"]), "lon": float(loc["lon"])}


def fetch_forecast_for_location(lat: float, lon: float, days: int = 3) -> Dict[str, Any]:
    params = {
        "key": load_weather_key(),
        "q": f"{lat},{lon}",
        "days": days,
        "aqi": "no",
        "alerts": "yes",
    }
    resp = requests.get(WEATHER_BASE_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def compact_weather(raw: Dict[str, Any]) -> Dict[str, Any]:
    # Location
    loc = raw.get("location", {})
    location = {
        "name": loc.get("name"),
        "region": loc.get("region"),
        "country": loc.get("country"),
        "lat": loc.get("lat"),
        "lon": loc.get("lon"),
        "tz_id": loc.get("tz_id"),
    }

    # Current
    cur = raw.get("current", {})
    current = {
        "temp_f": cur.get("temp_f"),
        "feelslike_f": cur.get("feelslike_f"),
        "condition": cur.get("condition", {}).get("text"),
        "wind_mph": cur.get("wind_mph"),
        "gust_mph": cur.get("gust_mph"),
        "humidity": cur.get("humidity"),
    }

    forecast = raw.get("forecast", {}) or {}
    forecastday = forecast.get("forecastday", []) or []

    # Forecast days (keep only fields we care about)
    forecast_days: List[Dict[str, Any]] = []
    for day_obj in forecastday:
        day_info = day_obj.get("day", {})
        forecast_days.append(
            {
                "date": day_obj.get("date"),
                "maxtemp_f": day_info.get("maxtemp_f"),
                "mintemp_f": day_info.get("mintemp_f"),
                "avgtemp_f": day_info.get("avgtemp_f"),
                "daily_chance_of_rain": day_info.get("daily_chance_of_rain"),
                "daily_chance_of_snow": day_info.get("daily_chance_of_snow"),
                "totalprecip_in": day_info.get("totalprecip_in"),
                "condition": day_info.get("condition", {}).get("text"),
                "uv": day_info.get("uv"),
            }
        )

    # Sunrise/sunset for current day only (from first forecastday.astro if present)
    sunrise = None
    sunset = None
    if forecastday:
        astro = forecastday[0].get("astro", {}) or {}
        sunrise = astro.get("sunrise")
        sunset = astro.get("sunset")

    # Alerts (if present)
    alerts_raw = raw.get("alerts", {})
    alerts_list = alerts_raw.get("alert", []) if isinstance(alerts_raw, dict) else []

    alerts_compact: List[Dict[str, Any]] = []
    for a in alerts_list:
        alerts_compact.append(
            {
                "headline": a.get("headline"),
                "severity": a.get("severity"),
                "event": a.get("event"),
                "effective": a.get("effective"),
                "expires": a.get("expires"),
            }
        )

    return {
        "location": location,
        "current": current,
        "forecast_days": forecast_days,
        "sunrise": sunrise,
        "sunset": sunset,
        "alerts": alerts_compact,
    }



def save_weather(raw: Any, park_dir: Path) -> None:
    compact = compact_weather(raw)
    out_path = park_dir / "weather.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(compact, f, indent=2)
    print(f"Saved {out_path}")


def fetch_weather_for_parks() -> None:
    for folder in ("YOSE", "ZION", "GRCA"):
        park_dir = NPS_DATA_ROOT / folder
        if not park_dir.exists():
            print(f"Skipping {folder}: directory does not exist (run nps_fetch_parks.py first)")
            continue

        coords = load_park_lat_lon(park_dir)
        lat, lon = coords["lat"], coords["lon"]
        print(f"{folder}: fetching weather for {lat},{lon}")
        raw = fetch_forecast_for_location(lat, lon, days=3)
        save_weather(raw, park_dir)


def main() -> None:
    fetch_weather_for_parks()


if __name__ == "__main__":
    main()
