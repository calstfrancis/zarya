import json
import urllib.parse
import urllib.request

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Violent showers",
    85: "Light snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Severe thunderstorm with hail",
}


def describe(code):
    return WEATHER_CODES.get(code, f"Weather code {code}")


def celsius_to_fahrenheit(c):
    return c * 9 / 5 + 32


def geocode(location):
    url = f"{GEOCODE_URL}?{urllib.parse.urlencode({'name': location, 'count': 1})}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
    results = data.get("results") or []
    if not results:
        raise ValueError(f"No location found for '{location}'")
    r = results[0]
    label = r["name"]
    if r.get("admin1"):
        label += f", {r['admin1']}"
    if r.get("country"):
        label += f", {r['country']}"
    return r["latitude"], r["longitude"], label


def fetch_today(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability",
        "timezone": "auto",
        "forecast_days": 1,
    }
    url = f"{FORECAST_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
    daily = data["daily"]
    hourly = data["hourly"]
    return {
        "code": daily["weather_code"][0],
        "temp_max_c": daily["temperature_2m_max"][0],
        "temp_min_c": daily["temperature_2m_min"][0],
        "hours": hourly["time"],
        "temp_c": hourly["temperature_2m"],
        "humidity": [v if v is not None else 0 for v in hourly["relative_humidity_2m"]],
        "precip_prob": [v if v is not None else 0 for v in hourly["precipitation_probability"]],
    }
