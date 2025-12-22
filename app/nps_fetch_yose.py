import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "data_samples" / "nps" / "YOSE"

BASE_URL = "https://developer.nps.gov/api/v1"


def load_api_key() -> str:
    load_dotenv(ENV_PATH)
    api_key = os.getenv("NPS_API_KEY")
    if not api_key:
        raise RuntimeError("NPS_API_KEY is not set in .env")
    return api_key


def nps_get(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    api_key = load_api_key()
    headers = {"X-Api-Key": api_key}
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    merged_params = {"limit": 50}
    if params:
        merged_params.update(params)

    resp = requests.get(url, headers=headers, params=merged_params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def save_json(data: Any, filename: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / filename
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {out_path}")


def get_yose_park_code() -> str:
    # Fetch Yosemite park record and cache to file
    data = nps_get("parks", {"q": "Yosemite", "limit": 10})
    save_json(data, "parks_search_yosemite.json")

    parks: List[Dict[str, Any]] = data.get("data", [])
    for park in parks:
        if "Yosemite National Park" in park.get("fullName", ""):
            return park["parkCode"]

    # Fallback: take first result
    if parks:
        return parks[0]["parkCode"]

    raise RuntimeError("Could not find Yosemite parkCode from NPS /parks search")


def fetch_yose_fixtures() -> None:
    park_code = get_yose_park_code()
    print(f"Using parkCode={park_code}")

    # Alerts (closures, safety, etc.)
    alerts = nps_get("alerts", {"parkCode": park_code, "limit": 50})
    save_json(alerts, "alerts.json")

    # Events (ranger programs, etc.)
    events = nps_get("events", {"parkCode": park_code, "limit": 50})
    save_json(events, "events.json")

    # Campgrounds (proxy for some amenities / overnight options)
    campgrounds = nps_get("campgrounds", {"parkCode": park_code, "limit": 50})
    save_json(campgrounds, "campgrounds.json")

    # Places – often includes points of interest, sometimes with accessibility info
    places = nps_get("places", {"parkCode": park_code, "limit": 50})
    save_json(places, "places.json")


def main() -> None:
    fetch_yose_fixtures()


if __name__ == "__main__":
    main()
