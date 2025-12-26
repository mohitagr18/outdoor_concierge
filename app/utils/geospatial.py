import math
from typing import List, Dict, Any

# Centroids for all 63 US National Parks (plus common abbreviations)
# Used to filter out "hallucinated" search results (e.g., Bandelier in GRCA)
PARK_CENTROIDS = {
    "ACAD": (44.3386, -68.2733), "ARCH": (38.7331, -109.5925), "BADL": (43.8554, -102.3397),
    "BIBE": (29.2498, -103.2502), "BISC": (25.4827, -80.1973), "BLCA": (38.5754, -107.7416),
    "BRCA": (37.5930, -112.1871), "CANY": (38.2136, -109.9325), "CARE": (38.2905, -111.2615),
    "CAVE": (32.1479, -104.5567), "CHIS": (34.0069, -119.7785), "CONG": (33.7935, -80.7815),
    "CRLA": (42.8684, -122.1685), "CUVA": (41.2804, -81.5678), "DENA": (63.1148, -151.1926),
    "DEVA": (36.5323, -116.9325), "DRTO": (24.6285, -82.8732), "EVER": (25.2866, -80.8987),
    "GAAR": (67.7833, -153.3000), "GATE": (38.5000, -90.0000), "GLAC": (48.7596, -113.7870), # Gateway Arch & Glacier
    "GLBA": (58.6658, -136.9002), "GRBA": (38.9833, -114.3000), "GRCA": (36.1069, -112.1129),
    "GRSA": (37.7916, -105.5943), "GRSM": (35.6131, -83.5532), "GUMO": (31.8715, -104.8606),
    "HALE": (20.7013, -156.1733), "HAVO": (19.4194, -155.2885), "HOSP": (34.5217, -93.0424),
    "INDU": (41.6533, -87.0524), "ISRO": (48.1011, -88.8247), "JOTR": (33.8734, -115.9010),
    "KATM": (58.5000, -155.0000), "KEFJ": (59.9167, -149.9833), "KICA": (36.7900, -118.5500), # Kings Canyon
    "KOVA": (67.5500, -159.2333), "LACL": (60.9667, -153.4167), "LAVO": (40.4977, -121.4207),
    "MACA": (37.1864, -86.1005), "MEVE": (37.2309, -108.4618), "MORA": (46.8800, -121.7269),
    "NOCA": (48.7718, -121.2985), "NPSA": (-14.2583, -170.6833), "OLYM": (47.8021, -123.6044),
    "PEFO": (34.9100, -109.8067), "PINN": (36.4906, -121.1825), "REDW": (41.2132, -124.0046),
    "ROMO": (40.3428, -105.6836), "SAGU": (32.2967, -111.1666), "SEKI": (36.4864, -118.5658),
    "SHEN": (38.4755, -78.4535), "THRO": (46.9729, -103.5387), "VIIS": (18.3338, -64.7333),
    "VOYA": (48.5059, -92.8884), "WICA": (43.5676, -103.4245), "WRST": (61.7104, -142.9857),
    "YELL": (44.4280, -110.5885), "YOSE": (37.8651, -119.5383), "ZION": (37.2982, -113.0263)
}

MAX_RADIUS_MILES = 50

# Fallback Entrances for tricky parks
FALLBACK_ENTRANCES = {
    "GRCA": [
        {"name": "South Entrance (Tusayan)", "lat": 36.0000, "lon": -112.1214, "type": "Entrance - Fallback"},
        {"name": "Desert View Entrance (East)", "lat": 36.0416, "lon": -111.8270, "type": "Entrance - Fallback"}
    ]
}

def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        R = 3958.8 
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    except (ValueError, TypeError):
        return 9999.9

def get_coords(item):
    """
    Extracts valid float lat/lon from an item.
    Handles:
    1. Flat Dict: {"latitude": "...", "longitude": "..."} (Raw JSON)
    2. Nested Location: {"location": {"lat": ..., "lon": ...}} (Pydantic dump)
    """
    lat = None
    lon = None

    # Check 1: Top-level keys (Raw JSON style)
    if "latitude" in item and "longitude" in item:
        lat = item["latitude"]
        lon = item["longitude"]
    
    # Check 2: Nested 'location' dict (Pydantic model_dump style)
    elif "location" in item and isinstance(item["location"], dict):
        loc = item["location"]
        # GeoLocation model uses 'lat', 'lon'
        if "lat" in loc: lat = loc.get("lat")
        if "lon" in loc: lon = loc.get("lon")
        # Fallback if Pydantic uses full names
        if "latitude" in loc and not lat: lat = loc.get("latitude")
        if "longitude" in loc and not lon: lon = loc.get("longitude")

    try:
        if lat is not None and lon is not None:
             # Ensure not empty string
             if str(lat).strip() == "" or str(lon).strip() == "":
                 return None, None
             return float(lat), float(lon)
    except (ValueError, TypeError):
        pass
    return None, None


def mine_entrances(park_code: str, places_data: List[Dict], vc_data: List[Dict]) -> List[Dict[str, Any]]:
    print(f"[DEBUG] Mining {park_code}. Input: {len(places_data)} Places, {len(vc_data)} VCs")
    
    raw_candidates = []
    
    # 1. Gather Candidates from Places
    for p in places_data:
        title = p.get("title", "") or p.get("name", "")
        t_lower = title.lower()
        
        blacklist = ["ev charging", "gas station", "market", "store", "parking", "stop", "amphitheater", "shuttle"]
        if any(term in t_lower for term in blacklist): 
            # print(f"[DEBUG] Blacklisted: {title}")
            continue
        
        whitelist = ["entrance", "visitor center", "information station", "welcome center"]
        if not any(term in t_lower for term in whitelist): 
            # print(f"[DEBUG] Not Whitelisted: {title}")
            continue
        
        lat, lon = get_coords(p)
        if lat:
            center = PARK_CENTROIDS.get(park_code.upper())
            if center:
                dist = calculate_distance(lat, lon, center[0], center[1])
                if dist > MAX_RADIUS_MILES:
                    print(f"[DEBUG] Outlier Dropped: {title} ({dist:.1f} miles)")
                    continue
            
            raw_candidates.append({
                "name": title, "lat": lat, "lon": lon,
                "type": "Entrance" if "entrance" in t_lower else "VisitorCenter"
            })
        else:
             if "entrance" in t_lower:
                 print(f"[DEBUG] Skipped (No Coords): {title}")
            
    # 2. Gather Candidates from VCs
    for v in vc_data:
        lat, lon = get_coords(v)
        if lat:
            # Check Outlier for VCs too
            center = PARK_CENTROIDS.get(park_code.upper())
            if center:
                dist = calculate_distance(lat, lon, center[0], center[1])
                if dist > MAX_RADIUS_MILES:
                    print(f"[DEBUG] VC Outlier Dropped: {v.get('name')} ({dist:.1f} miles)")
                    continue

            raw_candidates.append({
                "name": v.get("name", "VC"), "lat": lat, "lon": lon, "type": "VisitorCenter"
            })
        else:
            print(f"[DEBUG] VC Skipped (No Coords): {v.get('name')}")

    print(f"[DEBUG] Raw Candidates: {[c['name'] for c in raw_candidates]}")

    # ... (Dedupe & Dominance Logic same as before) ...
    # 3. Deduplicate
    unique = []
    raw_candidates.sort(key=lambda x: x["type"] == "Entrance", reverse=True)
    
    for c in raw_candidates:
        is_near = False
        for u in unique:
            if calculate_distance(c["lat"], c["lon"], u["lat"], u["lon"]) < 3.0:
                is_near = True
                break
        if not is_near:
            unique.append(c)

    # 4. Entrance Dominance
    final_list = []
    entrances = [x for x in unique if x["type"] == "Entrance"]
    vcs = [x for x in unique if x["type"] == "VisitorCenter"]
    
    final_list.extend(entrances)
    
    for vc in vcs:
        is_redundant = False
        for ent in entrances:
            if calculate_distance(vc["lat"], vc["lon"], ent["lat"], ent["lon"]) < 25.0:
                is_redundant = True
                break
        if not is_redundant:
            final_list.append(vc)
            
    print(f"[DEBUG] Final List: {[c['name'] for c in final_list]}")
    return final_list