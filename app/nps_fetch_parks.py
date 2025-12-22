import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DATA_ROOT = PROJECT_ROOT / "data_samples" / "nps"

BASE_URL = "https://developer.nps.gov/api/v1"


def load_api_key() -> str:
    load_dotenv(ENV_PATH)
    api_key = os.getenv("NPS_API_KEY")
    if not api_key:
        raise RuntimeError("NPS_API_KEY is not set in .env")
    return api_key


def nps_get(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    headers = {"X-Api-Key": load_api_key()}
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    merged_params: Dict[str, Any] = {"limit": 50}
    if params:
        merged_params.update(params)

    resp = requests.get(url, headers=headers, params=merged_params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def save_json(data: Any, out_dir: Path, filename: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {out_path}")


def resolve_park_code(hint: str) -> str:
    data = nps_get("parks", {"q": hint, "limit": 10})
    parks: List[Dict[str, Any]] = data.get("data", [])
    if not parks:
        raise RuntimeError(f"No parks found for hint={hint!r}")
    # Prefer exact fullName match if possible
    for park in parks:
        if "Yosemite National Park" in park.get("fullName", "") and "Yosemite" in hint:
            return park["parkCode"]
        if "Zion National Park" in park.get("fullName", "") and "Zion" in hint:
            return park["parkCode"]
        if "Grand Canyon National Park" in park.get("fullName", "") and "Grand Canyon" in hint:
            return park["parkCode"]
    return parks[0]["parkCode"]

def nps_get_all(endpoint: str, base_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Fetch all pages for an endpoint that supports limit/total/start.
    Returns a dict with the same shape as NPS, but with all data concatenated.
    """
    headers = {"X-Api-Key": load_api_key()}
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"

    all_data = []
    start = 0
    limit = 50  # NPS default/maximum in many endpoints

    while True:
        params: Dict[str, Any] = {"limit": limit, "start": start}
        if base_params:
            params.update(base_params)

        resp = requests.get(url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        page = resp.json()

        data_page = page.get("data", [])
        all_data.extend(data_page)

        total = int(page.get("total", len(all_data)))
        start += limit

        if start >= total or not data_page:
            # Build a merged response object
            merged = dict(page)
            merged["data"] = all_data
            merged["limit"] = str(limit)
            merged["start"] = "0"
            merged["total"] = str(total)
            return merged


def fetch_park_fixtures(park_hint: str, folder_name: str) -> None:
    park_dir = DATA_ROOT / folder_name
    parks_search = nps_get("parks", {"q": park_hint, "limit": 10})
    save_json(parks_search, park_dir, "parks_search.json")

    parks: List[Dict[str, Any]] = parks_search.get("data", [])
    if not parks:
        raise RuntimeError(f"No parks found for hint={park_hint!r}")

    park_code = resolve_park_code(park_hint)
    print(f"{park_hint}: using parkCode={park_code}")

    alerts = nps_get("alerts", {"parkCode": park_code})
    save_json(alerts, park_dir, "alerts.json")

    events = nps_get("events", {"parkCode": park_code})
    save_json(events, park_dir, "events.json")

    campgrounds = nps_get("campgrounds", {"parkCode": park_code})
    save_json(campgrounds, park_dir, "campgrounds.json")

    places = nps_get_all("places", {"parkCode": park_code})
    save_json(places, park_dir, "places.json")

    # roadevents = nps_get("roadevents", {"parkCode": park_code})
    # save_json(roadevents, park_dir, "roadevents.json")

    thingstodo = nps_get("thingstodo", {"parkCode": park_code})
    save_json(thingstodo, park_dir, "thingstodo.json")

    passportstamps = nps_get("passportstamplocations", {"parkCode": park_code})
    save_json(passportstamps, park_dir, "passportstamplocations.json")

    visitorcenters = nps_get("visitorcenters", {"parkCode": park_code})
    save_json(visitorcenters, park_dir, "visitorcenters.json")

    webcams = nps_get("webcams", {"parkCode": park_code})
    save_json(webcams, park_dir, "webcams.json")



def main() -> None:
    parks = [
        ("Yosemite", "YOSE"),
        ("Zion", "ZION"),
        ("Grand Canyon", "GRCA"),
    ]
    for hint, folder in parks:
        fetch_park_fixtures(hint, folder)


if __name__ == "__main__":
    main()
