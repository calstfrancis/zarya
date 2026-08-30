import json
import urllib.parse
import urllib.request

STATIONS_URL = "https://api.weather.gc.ca/collections/aqhi-stations/items"
OBSERVATIONS_URL = "https://api.weather.gc.ca/collections/aqhi-observations-realtime/items"


def _nearest_station(lat, lon):
    delta = 0.5
    data = None
    for _ in range(6):
        bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"
        params = {"f": "json", "bbox": bbox, "limit": 50}
        url = f"{STATIONS_URL}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.load(resp)
        if data.get("features"):
            break
        delta *= 2
    if not data or not data.get("features"):
        return None

    best = None
    best_dist = None
    for feature in data["features"]:
        station_lon, station_lat = feature["geometry"]["coordinates"]
        dist = (station_lon - lon) ** 2 + (station_lat - lat) ** 2
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best = feature
    return best


def fetch_current_aqhi(lat, lon):
    station = _nearest_station(lat, lon)
    if station is None:
        return None

    location_id = station["properties"]["location_id"]
    params = {"f": "json", "location_id": location_id, "latest": "true"}
    url = f"{OBSERVATIONS_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
    features = data.get("features") or []
    if not features:
        return None

    props = features[0]["properties"]
    value = props.get("aqhi")
    if value is None:
        return None
    category, css_class = _category(value)
    return {
        "value": value,
        "station": props.get("location_name_en") or station["properties"].get("location_name_en"),
        "category": category,
        "css_class": css_class,
    }


def _category(value):
    # Canada's official AQHI scale: 1-3 Low, 4-6 Moderate, 7-10 High, 10+ Very High.
    # css_class picks a distinct colored badge per tier (see styles.py's
    # .aqhi-* rules), not just the generic accent/warning/error trio, so the
    # four tiers actually read as four different colors, not two.
    if value <= 3:
        return "Low", "aqhi-low"
    if value <= 6:
        return "Moderate", "aqhi-moderate"
    if value <= 10:
        return "High", "aqhi-high"
    return "Very High", "aqhi-very-high"
