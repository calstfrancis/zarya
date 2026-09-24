import math
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gtk

# Fondwave — Cal's dusk palette (see fondwave-palette.html), used here for one
# deliberately-branded card rather than general app chrome; everything else
# still routes through libadwaita's named colors per house convention.
NIGHT_INDIGO = "#3C2F5C"
DEEP_INDIGO = "#4E3E76"
DEEP_BERRY = "#8B2F5C"
CORAL_RED = "#E2604A"
PEACH_TAN = "#E8B87E"
IVORY_DAWN = "#FAF3E8"
CREAM_LABEL = "#F6ECD9"

# Fondwave.colorscheme (Konsole) — the light/cream variant, reproduced here
# directly so the log view matches it even on a machine that never installed
# the actual Konsole profile. Background/foreground are the canonical
# palette; the ANSI-derived accents (dark sage/teal) only exist in the
# Konsole scheme, not the core Fondwave hex list.
TERMINAL_BG = "#F0E6D8"
TERMINAL_FG = "#4A3B56"
TERMINAL_RED = "#8B2F5C"
TERMINAL_GREEN = "#495D47"
TERMINAL_CYAN = "#425662"

# Six dark-to-light stops the weather card's gradient slides across as the
# day goes from night to noon and back — see `_gradient_stops` below. Index 0
# is the darkest (deep night), index 5 the lightest (full daylight).
_GRADIENT_RAMP = [NIGHT_INDIGO, DEEP_INDIGO, DEEP_BERRY, CORAL_RED, PEACH_TAN, IVORY_DAWN]
_GRADIENT_POSITIONS = [0, 28, 58, 82, 100]


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _lerp_hex(a: str, b: str, t: float) -> str:
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)
    return "#{:02X}{:02X}{:02X}".format(
        round(ar + (br - ar) * t), round(ag + (bg - ag) * t), round(ab + (bb - ab) * t)
    )


def daylight_factor(
    now: datetime | None = None,
    sunrise_hour: float | None = None,
    sunset_hour: float | None = None,
) -> float:
    """0.0 while it's dark out, 1.0 at solar noon, smooth in between —
    lines up with the *actual* length of today's daylight (from
    `weather.sun_hours`) rather than assuming a fixed 12-hour day centered
    on clock-noon. Before sunrise or after sunset it's flat 0.0 (already the
    ramp's darkest end, so there's no need for a separate night-time curve);
    between them it's a half-sine arc from 0 at sunrise, through 1 at the
    midpoint (which is solar noon by construction), back to 0 at sunset.

    Falls back to the old fixed-noon cosine curve if sunrise/sunset aren't
    known yet (before weather has loaded) — a reasonable default, just not
    tied to a real day length.
    """
    now = now or datetime.now()
    hour = now.hour + now.minute / 60
    if sunrise_hour is None or sunset_hour is None or sunset_hour <= sunrise_hour:
        return 0.5 - 0.5 * math.cos(hour / 24 * 2 * math.pi)
    if sunrise_hour <= hour <= sunset_hour:
        return math.sin(math.pi * (hour - sunrise_hour) / (sunset_hour - sunrise_hour))
    return 0.0


def _gradient_stops(factor: float) -> list[str]:
    # Slides a 5-color window across the 6-color ramp: factor=0 uses ramp
    # colors [0..4] (darkest), factor=1 uses [1..5] (lightest), so the whole
    # gradient shifts one step lighter as daylight increases.
    return [_lerp_hex(_GRADIENT_RAMP[i], _GRADIENT_RAMP[i + 1], factor) for i in range(5)]


# rain: cool blue-gray; snow: pale, closer to white. RGB components only —
# alpha comes from weather.precip_tint()'s per-code intensity.
_PRECIP_COLORS = {"rain": "74, 85, 104", "snow": "218, 225, 231"}


def _precip_overlay_css(precip: tuple[str, float] | None) -> str:
    if precip is None:
        return ""
    kind, alpha = precip
    rgb = _PRECIP_COLORS.get(kind)
    if rgb is None:
        return ""
    return f"linear-gradient(135deg, rgba({rgb}, {alpha}) 0%, rgba({rgb}, {alpha * 0.4}) 100%), "


def weather_gradient_css(
    factor: float | None = None,
    sunrise_hour: float | None = None,
    sunset_hour: float | None = None,
    precip: tuple[str, float] | None = None,
) -> str:
    if factor is None:
        factor = daylight_factor(sunrise_hour=sunrise_hour, sunset_hour=sunset_hour)
    stops = _gradient_stops(factor)
    stop_list = ", ".join(f"{color} {pos}%" for color, pos in zip(stops, _GRADIENT_POSITIONS))
    overlay = _precip_overlay_css(precip)
    return f".fondwave-card {{ background-image: {overlay}linear-gradient(135deg, {stop_list}); }}"


FONDWAVE_CSS = f"""
.fondwave-card {{
  border-radius: 12px;
  padding: 10px 12px;
}}
.fondwave-card label {{ color: {IVORY_DAWN}; }}
.fondwave-card label.dim-label {{ color: {CREAM_LABEL}; opacity: 0.8; }}
.fondwave-card label.accent {{ color: {IVORY_DAWN}; font-weight: 800; }}
.fondwave-card button {{ color: {IVORY_DAWN}; }}
.fondwave-card label.warning {{ color: #FFD166; font-weight: 700; }}
.fondwave-card label.error {{ color: #FF6B6B; font-weight: 700; }}
.fondwave-card scrollbar {{ opacity: 0.6; }}

/* Weather "hero" row — the big current temperature, condition, and the
   sunrise/sunset/moon pill, matching the mockup's weather layout. */
.fondwave-card label.weather-hero-temp {{
  font-size: 2.4em;
  font-weight: 300;
  letter-spacing: -0.02em;
}}
.fondwave-card label.weather-hero-condition {{
  font-size: 1.15em;
  font-weight: 600;
}}
.fondwave-card .weather-sun-pill {{
  background-color: rgba(36, 22, 54, 0.35);
  border-radius: 10px;
  padding: 6px 12px;
}}

/* Color-coded AQI badges — the six official US EPA AQI tiers, not just the
   generic accent/warning/error trio, so each reads as a genuinely
   different color at a glance. */
.fondwave-card label.aqi-good {{
  background-color: #4CAF50; color: #FFFFFF; font-weight: 800;
  border-radius: 999px; padding: 2px 10px;
}}
.fondwave-card label.aqi-moderate {{
  background-color: #FBC02D; color: {NIGHT_INDIGO}; font-weight: 800;
  border-radius: 999px; padding: 2px 10px;
}}
.fondwave-card label.aqi-unhealthy-sensitive {{
  background-color: #FF8F00; color: #FFFFFF; font-weight: 800;
  border-radius: 999px; padding: 2px 10px;
}}
.fondwave-card label.aqi-unhealthy {{
  background-color: #E53935; color: #FFFFFF; font-weight: 800;
  border-radius: 999px; padding: 2px 10px;
}}
.fondwave-card label.aqi-very-unhealthy {{
  background-color: #8E24AA; color: #FFFFFF; font-weight: 800;
  border-radius: 999px; padding: 2px 10px;
}}
.fondwave-card label.aqi-hazardous {{
  background-color: #6D1B1B; color: #FFFFFF; font-weight: 800;
  border-radius: 999px; padding: 2px 10px;
}}

.weather-figures label {{ font-feature-settings: "tnum"; }}

/* The current-hour column in the weather table — a filled pill, not just
   bold text, so "now" actually stands out while scanning the row. */
.fondwave-card label.now-hour {{
  background-color: rgba(255, 255, 255, 0.28);
  color: {IVORY_DAWN};
  font-weight: 800;
  border-radius: 6px;
  padding: 1px 5px;
}}

.changelog-text, .changelog-text text {{
  background: transparent;
}}
.changelog-text {{
  padding: 0;
}}

.fondwave-terminal, .fondwave-terminal textview, .fondwave-terminal textview text {{
  background-color: {TERMINAL_BG};
  color: {TERMINAL_FG};
}}
.fondwave-terminal textview text selection {{
  background-color: {TERMINAL_FG};
  color: {TERMINAL_BG};
}}

/* Status cards (System/Backups/Updates) — always a visible card (same
   look as libadwaita's own `.card`), so it reads as a distinct tappable
   element even when there's nothing to report; only the *color* is quiet
   until there's actually something to flag. Named colors throughout, so
   this recolors for free in dark mode / any accent — no hardcoded hexes
   for the neutral state. */
.status-card {{
  background-color: @card_bg_color;
  color: @card_fg_color;
  border: 1px solid @borders;
  border-radius: 12px;
  padding: 8px 10px;
}}
.status-card:hover {{
  background-color: alpha(@window_fg_color, 0.03);
}}
.status-card.warning {{
  background-color: alpha(#e5a50a, 0.12);
  border-color: alpha(#e5a50a, 0.4);
}}
.status-card.error {{
  background-color: alpha(#e01b24, 0.1);
  border-color: alpha(#e01b24, 0.35);
}}
.status-card .status-card-title {{ font-size: 0.85em; opacity: 0.75; }}
.status-card .status-card-value {{ font-weight: 700; }}
.status-card.warning .status-card-value {{ color: #9c6e03; }}
.status-card.error .status-card-value {{ color: #a51d2d; }}

/* A small "now" divider in Today's Events, between past and future items. */
.now-marker-line {{ background-color: #3584e4; min-height: 2px; border-radius: 1px; }}
.now-marker-label {{ color: #3584e4; font-weight: 700; }}

/* Deterministic per-calendar dot colors (index = hash(calendar_id) % 6) —
   not Google's own calendar colors (a separate, extra API field), just
   enough for same-calendar events to visually match each other. */
.cal-dot-0, .cal-dot-1, .cal-dot-2, .cal-dot-3, .cal-dot-4, .cal-dot-5 {{
  border-radius: 999px;
}}
.cal-dot-0 {{ background-color: #3584e4; }}
.cal-dot-1 {{ background-color: #26a269; }}
.cal-dot-2 {{ background-color: #c64600; }}
.cal-dot-3 {{ background-color: #9141ac; }}
.cal-dot-4 {{ background-color: #8B2F5C; }}
.cal-dot-5 {{ background-color: #1a5fb4; }}

/* Disk usage bars in the System card. libadwaita's own LevelBar offset
   classes (.low/.high/.full) are the wrong semantic here — they colour
   "full" as success-green, meant for meters where low is the bad end
   (battery, volume). A full disk is the bad end, so severity is driven
   directly from our own warning/critical thresholds instead of GTK's
   offsets (never added), overriding the default not-empty (accent blue)
   fill color only when actually warning/critical. */
levelbar.disk-level.warning trough > block:not(.empty) {{ background-color: #e5a50a; }}
levelbar.disk-level.error trough > block:not(.empty) {{ background-color: #e01b24; }}
"""


def _find_fond_css() -> Path | None:
    """Locate the vendored copy of the Fond suite's shared stylesheet.

    Same two-location fallback as CHANGELOG.md and the app icon: the flatpak
    build copies ``style/fond.css`` from the git checkout into
    ``zarya/data/fond.css`` before ``pip install`` (see
    ``io.github.calstfrancis.zarya.yml``), while a plain ``pip install -e .``
    dev checkout only has the ``style/`` copy. A missing stylesheet isn't
    worth refusing to start over — Zarya is usable unstyled.
    """
    p = Path(__file__).resolve().parent.parent / "style" / "fond.css"
    if p.exists():
        return p
    try:
        import importlib.resources
        ref = importlib.resources.files("zarya.data").joinpath("fond.css")
        with importlib.resources.as_file(ref) as p2:
            if p2.exists():
                return p2
    except (ImportError, ModuleNotFoundError, FileNotFoundError):
        pass
    return None


def apply():
    display = Gdk.Display.get_default()
    if display is None:
        return

    fond_path = _find_fond_css()
    if fond_path is not None:
        fond_provider = Gtk.CssProvider()
        fond_provider.load_from_data(fond_path.read_text().encode())
        Gtk.StyleContext.add_provider_for_display(
            display, fond_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    provider = Gtk.CssProvider()
    provider.load_from_string(FONDWAVE_CSS)
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    global _gradient_provider
    _gradient_provider = Gtk.CssProvider()
    Gtk.StyleContext.add_provider_for_display(
        display, _gradient_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    refresh_weather_gradient()


_gradient_provider: Gtk.CssProvider | None = None
_sunrise_hour: float | None = None
_sunset_hour: float | None = None
_precip: tuple[str, float] | None = None


def set_sun_hours(sunrise_hour: float | None, sunset_hour: float | None):
    """Called once today's weather has loaded, with today's real sunrise and
    sunset (`weather.sun_hours`) — falls back to the fixed-noon curve if
    weather hasn't loaded yet or the fetch omitted them."""
    global _sunrise_hour, _sunset_hour
    _sunrise_hour, _sunset_hour = sunrise_hour, sunset_hour
    refresh_weather_gradient()


def set_precip_tint(precip: tuple[str, float] | None):
    """Called once today's weather has loaded, with `weather.precip_tint()`
    for the current conditions — None clears the overlay."""
    global _precip
    _precip = precip
    refresh_weather_gradient()


def refresh_weather_gradient():
    """Recompute the weather card's gradient for the current time of day.

    Call this periodically (see `ZaryaWindow`'s gradient timer) — the
    provider itself is updated in place rather than re-added, so this never
    stacks duplicate providers on the display.
    """
    if _gradient_provider is not None:
        _gradient_provider.load_from_string(
            weather_gradient_css(sunrise_hour=_sunrise_hour, sunset_hour=_sunset_hour, precip=_precip)
        )
