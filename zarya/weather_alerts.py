import datetime
import json
import urllib.parse
import urllib.request

ALERTS_URL = "https://api.weather.gc.ca/collections/weather-alerts/items"

# Environment Canada only — this API has no coverage outside Canada, so for
# a non-Canadian location fetch_active_alerts() just returns an empty list
# (the bbox query legitimately matches nothing), not an error.
_INACTIVE_STATUSES = {"ended"}


def fetch_active_alerts(lat, lon):
    # A small bbox around the point acts as a point-in-polygon test: alert
    # zones are large regions, so any zone containing the point intersects
    # even a tiny box centered on it.
    delta = 0.05
    bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"
    params = {"f": "json", "bbox": bbox, "limit": 20}
    url = f"{ALERTS_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)

    now = datetime.datetime.now(datetime.timezone.utc)
    alerts = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        if props.get("status_en") in _INACTIVE_STATUSES:
            continue
        expiration = _parse_datetime(props.get("expiration_datetime"))
        if expiration is not None and expiration < now:
            continue
        alerts.append({
            "headline": props.get("alert_short_name_en") or props.get("alert_name_en") or "Weather alert",
            "type": props.get("alert_type", ""),
            "text": props.get("alert_text_en") or "",
            "risk_colour": (props.get("risk_colour_en") or "").lower(),
            "region": props.get("feature_name_en") or "",
        })
    return alerts


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
