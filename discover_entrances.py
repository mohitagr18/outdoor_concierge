import os
import json
import logging
import math

# Config
DATA_DIR = "data_samples/nps"
PARKS = ["YOSE", "ZION", "GRCA"]

# Approximate Centroids to filter hallucinations
PARK_CENTROIDS = {
    "YOSE": (37.8651, -119.5383),
    "ZION": (37.2982, -113.0263),
    "GRCA": (36.0544, -112.1401)
}
MAX_RADIUS_MILES = 50

logging.basicConfig(level=logging.INFO, format='%(message)s')

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 3958.8 
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def load_json(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data if isinstance(data, list) else []
    except Exception:
        return []

def get_coords(item):
    try:
        lat = item.get("latitude")
        lon = item.get("longitude")
        if lat and lon and str(lat).strip() and str(lon).strip():
            return float(lat), float(lon)
    except (ValueError, TypeError):
        pass
    return None, None

def mine_entrances(park_code):
    base = os.path.join(DATA_DIR, park_code)
    raw_candidates = []

    # Load All Candidates (VCs + Places)
    sources = [
        ("visitorcenters.json", "VisitorCenter"),
        ("places.json", "Place")
    ]

    for filename, source_type in sources:
        items = load_json(os.path.join(base, filename))
        for item in items:
            title = item.get("title") or item.get("name") or "Unknown"
            t_lower = title.lower()

            # --- STRICT FILTERS ---
            blacklist = ["ev charging", "gas station", "market", "store", "parking", "stop", "amphitheater", "shuttle"]
            if any(term in t_lower for term in blacklist):
                continue

            whitelist = ["entrance", "visitor center", "information station", "welcome center"]
            if not any(term in t_lower for term in whitelist):
                continue

            lat, lon = get_coords(item)
            if not lat:
                continue

            # Outlier Check
            center = PARK_CENTROIDS.get(park_code)
            if center:
                dist = calculate_distance(lat, lon, center[0], center[1])
                if dist > MAX_RADIUS_MILES:
                    continue

            raw_candidates.append({
                "name": title,
                "lat": lat,
                "lon": lon,
                "type": "Entrance" if "entrance" in t_lower else "VisitorCenter"
            })

    # Deduplicate (Spatial)
    unique = []
    # Prioritize Entrances
    raw_candidates.sort(key=lambda x: x["type"] == "Entrance", reverse=True)

    for c in raw_candidates:
        is_near = False
        for u in unique:
            if calculate_distance(c["lat"], c["lon"], u["lat"], u["lon"]) < 3.0:
                is_near = True
                break
        if not is_near:
            unique.append(c)

    # --- ENTRANCE DOMINANCE RULE ---
    # If a VisitorCenter is within 25 miles of an Entrance, Drop the VC.
    entrances = [x for x in unique if x["type"] == "Entrance"]
    vcs = [x for x in unique if x["type"] == "VisitorCenter"]

    final_list = []
    final_list.extend(entrances)

    for vc in vcs:
        is_redundant = False
        for ent in entrances:
            if calculate_distance(vc["lat"], vc["lon"], ent["lat"], ent["lon"]) < 25.0:
                is_redundant = True
                break
        if not is_redundant:
            final_list.append(vc)

    return final_list

def main():
    print("--- 🌲 Final Entrance Logic Test (With Coords) 🌲 ---")
    for park in PARKS:
        print(f"[{park}] Results:")
        entrances = mine_entrances(park)
        if not entrances:
            print("  ⚠️ No valid entrances found.")
        for e in entrances:
            print(f"  📍 {e['name']} ({e['type']})")
            print(f"     Lat: {e['lat']:.5f}, Lon: {e['lon']:.5f}")
        print("")

if __name__ == "__main__":
    main()