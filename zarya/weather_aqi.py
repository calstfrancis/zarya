import json
import urllib.parse
import urllib.request

AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def fetch_current_aqi(lat, lon):
    """The standard US EPA AQI (0-500), not Canada's AQHI (1-10) — this is
    what every other weather app shows by default, so it's what a number
    typed into Zarya should match rather than a different, Canada-specific
    scale that just happens to also look like a small integer."""
    params = {"latitude": lat, "longitude": lon, "current": "us_aqi"}
    url = f"{AIR_QUALITY_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
    value = (data.get("current") or {}).get("us_aqi")
    if value is None:
        return None
    category, css_class = _category(value)
    return {"value": value, "category": category, "css_class": css_class}


def _category(value):
    # Official US EPA AQI breakpoints.
    if value <= 50:
        return "Good", "aqi-good"
    if value <= 100:
        return "Moderate", "aqi-moderate"
    if value <= 150:
        return "Unhealthy for Sensitive Groups", "aqi-unhealthy-sensitive"
    if value <= 200:
        return "Unhealthy", "aqi-unhealthy"
    if value <= 300:
        return "Very Unhealthy", "aqi-very-unhealthy"
    return "Hazardous", "aqi-hazardous"
