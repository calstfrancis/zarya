import datetime
import json
import math
import urllib.parse
import urllib.request

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# A known new moon (2000-01-06 18:14 UTC) plus the synodic month's average
# length — a plain astronomical formula, no API/network call needed. Good
# enough for a dashboard reading (accurate to well under a day), not for
# anything that needs precision.
_KNOWN_NEW_MOON = datetime.datetime(2000, 1, 6, 18, 14, tzinfo=datetime.timezone.utc)
_SYNODIC_MONTH_DAYS = 29.530588861

_MOON_PHASES = [
    (0.03, "New Moon", "🌑"),
    (0.22, "Waxing Crescent", "🌒"),
    (0.28, "First Quarter", "🌓"),
    (0.47, "Waxing Gibbous", "🌔"),
    (0.53, "Full Moon", "🌕"),
    (0.72, "Waning Gibbous", "🌖"),
    (0.78, "Last Quarter", "🌗"),
    (0.97, "Waning Crescent", "🌘"),
]


def moon_phase(now: datetime.datetime | None = None) -> dict:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    days = (now - _KNOWN_NEW_MOON).total_seconds() / 86400
    fraction = (days % _SYNODIC_MONTH_DAYS) / _SYNODIC_MONTH_DAYS
    illumination = (1 - math.cos(2 * math.pi * fraction)) / 2 * 100
    name, emoji = next(
        ((n, e) for threshold, n, e in _MOON_PHASES if fraction < threshold),
        ("New Moon", "🌑"),
    )
    return {"fraction": fraction, "illumination": illumination, "name": name, "emoji": emoji}

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


def format_sun_time(iso_str):
    if not iso_str:
        return None
    try:
        # 12-hour with am/pm reads more naturally than 24-hour for a
        # sunrise/sunset line ("7:03 AM" vs "07:03") — %-I drops the
        # leading zero.
        return datetime.datetime.fromisoformat(iso_str).strftime("%-I:%M %p")
    except ValueError:
        return None


def sun_hours(sunrise_iso, sunset_iso):
    """(sunrise_hour, sunset_hour) as fractional hours (e.g. (7.1, 19.2)),
    or (None, None) if either is missing — feeds the weather gradient's
    daylight curve so it actually lines up with today's real sunrise/sunset
    instead of assuming a fixed 12-hour day centered on noon."""
    try:
        sunrise = datetime.datetime.fromisoformat(sunrise_iso)
        sunset = datetime.datetime.fromisoformat(sunset_iso)
    except (TypeError, ValueError):
        return None, None
    return (
        sunrise.hour + sunrise.minute / 60,
        sunset.hour + sunset.minute / 60,
    )


def day_length_minutes(sunrise_iso, sunset_iso):
    try:
        sunrise = datetime.datetime.fromisoformat(sunrise_iso)
        sunset = datetime.datetime.fromisoformat(sunset_iso)
    except (TypeError, ValueError):
        return None
    return (sunset - sunrise).total_seconds() / 60


def day_length_delta_minutes(today_sunrise, today_sunset, yesterday_sunrise, yesterday_sunset):
    """Minutes more (positive) or less (negative) daylight than yesterday,
    or None if either day's sunrise/sunset is missing. Both days' data
    already come from the same `fetch_today()` call (via `past_days=1`),
    so this needs no extra network request."""
    today_len = day_length_minutes(today_sunrise, today_sunset)
    yesterday_len = day_length_minutes(yesterday_sunrise, yesterday_sunset)
    if today_len is None or yesterday_len is None:
        return None
    return today_len - yesterday_len


# code -> (kind, alpha) for the weather card's precipitation tint overlay.
# Alpha increases with intensity (light/moderate/heavy variants of the same
# code family) — a plain, hand-picked scale, not derived from actual
# rainfall-rate physics.
_PRECIP_TINTS = {
    51: ("rain", 0.12), 53: ("rain", 0.16), 55: ("rain", 0.20),
    56: ("rain", 0.14), 57: ("rain", 0.18),
    61: ("rain", 0.16), 63: ("rain", 0.22), 65: ("rain", 0.30),
    66: ("rain", 0.18), 67: ("rain", 0.26),
    80: ("rain", 0.18), 81: ("rain", 0.24), 82: ("rain", 0.32),
    95: ("rain", 0.28), 96: ("rain", 0.32), 99: ("rain", 0.36),
    71: ("snow", 0.14), 73: ("snow", 0.20), 75: ("snow", 0.28), 77: ("snow", 0.12),
    85: ("snow", 0.18), 86: ("snow", 0.26),
}


def precip_tint(code):
    """(kind, alpha) for the current weather code if it's actively
    precipitating, else None — `kind` is "rain" or "snow", used to pick the
    overlay tint color."""
    return _PRECIP_TINTS.get(code)


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
    # past_days=1 + forecast_days=2 gives three full days (yesterday, today,
    # tomorrow) so the ±12h hourly window below always has enough on either
    # side of "now" to slice from, however close to midnight "now" is.
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability",
        "current": "temperature_2m,apparent_temperature,weather_code,precipitation",
        "timezone": "auto",
        "past_days": 1,
        "forecast_days": 2,
    }
    url = f"{FORECAST_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
    daily = data["daily"]
    hourly = data["hourly"]
    current = data.get("current") or {}

    # `past_days=1` shifts the `daily` arrays too — index 0 is now
    # yesterday, not today. Today is always at index 1 (exactly one past
    # day is always inserted ahead of it).
    TODAY_INDEX = 1

    # Find "now" in the hourly series (matched on date+hour, not hour alone
    # — several entries share the same hour-of-day once the window below
    # can span two calendar days) and slice to the 12 hours before and
    # after it, inclusive of "now" itself (25 points total).
    now_prefix = datetime.datetime.now().strftime("%Y-%m-%dT%H")
    now_idx = next(
        (i for i, t in enumerate(hourly["time"]) if t.startswith(now_prefix)),
        len(hourly["time"]) // 2,  # shouldn't happen; degrade to the window's middle
    )
    lo, hi = max(0, now_idx - 12), min(len(hourly["time"]), now_idx + 13)

    # "auto" timezone makes these local ISO timestamps (e.g.
    # "2026-09-24T06:42"), same as the hourly series above. Index 0 (not
    # shifted like TODAY_INDEX) is yesterday, already present in this same
    # response thanks to past_days=1 — used for the day-length delta below,
    # no extra request needed.
    sunrise = daily.get("sunrise", [None] * (TODAY_INDEX + 1))[TODAY_INDEX]
    sunset = daily.get("sunset", [None] * (TODAY_INDEX + 1))[TODAY_INDEX]
    sunrise_yesterday = daily.get("sunrise", [None])[0]
    sunset_yesterday = daily.get("sunset", [None])[0]

    return {
        "code": daily["weather_code"][TODAY_INDEX],
        "temp_max_c": daily["temperature_2m_max"][TODAY_INDEX],
        "temp_min_c": daily["temperature_2m_min"][TODAY_INDEX],
        "sunrise": sunrise,
        "sunset": sunset,
        "sunrise_yesterday": sunrise_yesterday,
        "sunset_yesterday": sunset_yesterday,
        "hours": hourly["time"][lo:hi],
        "temp_c": hourly["temperature_2m"][lo:hi],
        "humidity": [v if v is not None else 0 for v in hourly["relative_humidity_2m"][lo:hi]],
        "precip_prob": [v if v is not None else 0 for v in hourly["precipitation_probability"][lo:hi]],
        "current_temp_c": current.get("temperature_2m"),
        "feels_like_c": current.get("apparent_temperature"),
        "current_code": current.get("weather_code"),
        "current_precip_mm": current.get("precipitation"),
    }
