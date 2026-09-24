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


def daylight_factor(now: datetime | None = None, solar_noon_hour: float = 12.0) -> float:
    """0.0 at the darkest point of the day, 1.0 at solar noon, smooth in
    between. `solar_noon_hour` defaults to a plain clock-noon assumption;
    pass the real midpoint of today's sunrise/sunset (from
    `weather.solar_noon_hour`) once it's known, to phase-shift the curve to
    the actual solar day instead of assuming exactly 12:00.
    """
    now = now or datetime.now()
    hour = now.hour + now.minute / 60
    return 0.5 - 0.5 * math.cos((hour - solar_noon_hour + 12) / 24 * 2 * math.pi)


def _gradient_stops(factor: float) -> list[str]:
    # Slides a 5-color window across the 6-color ramp: factor=0 uses ramp
    # colors [0..4] (darkest), factor=1 uses [1..5] (lightest), so the whole
    # gradient shifts one step lighter as daylight increases.
    return [_lerp_hex(_GRADIENT_RAMP[i], _GRADIENT_RAMP[i + 1], factor) for i in range(5)]


def weather_gradient_css(factor: float | None = None, solar_noon_hour: float = 12.0) -> str:
    if factor is None:
        factor = daylight_factor(solar_noon_hour=solar_noon_hour)
    stops = _gradient_stops(factor)
    stop_list = ", ".join(f"{color} {pos}%" for color, pos in zip(stops, _GRADIENT_POSITIONS))
    return f".fondwave-card {{ background-image: linear-gradient(135deg, {stop_list}); }}"


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
_solar_noon_hour = 12.0


def set_solar_noon_hour(hour: float | None):
    """Called once today's weather has loaded, with the real midpoint of
    sunrise/sunset (`weather.solar_noon_hour`) — falls back to the plain
    12:00 assumption if weather hasn't loaded yet or the fetch omitted it."""
    global _solar_noon_hour
    _solar_noon_hour = hour if hour is not None else 12.0
    refresh_weather_gradient()


def refresh_weather_gradient():
    """Recompute the weather card's gradient for the current time of day.

    Call this periodically (see `ZaryaWindow`'s gradient timer) — the
    provider itself is updated in place rather than re-added, so this never
    stacks duplicate providers on the display.
    """
    if _gradient_provider is not None:
        _gradient_provider.load_from_string(weather_gradient_css(solar_noon_hour=_solar_noon_hour))
