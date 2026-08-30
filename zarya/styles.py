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

FONDWAVE_CSS = f"""
.fondwave-card {{
  background-image: linear-gradient(135deg,
    {NIGHT_INDIGO} 0%, {DEEP_INDIGO} 28%, {DEEP_BERRY} 58%,
    {CORAL_RED} 82%, {PEACH_TAN} 100%);
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

/* Color-coded AQI badges — a pill per Canada's AQHI tier, not just the
   generic accent/warning/error trio, so Low/Moderate/High/Very High each
   read as a genuinely different color at a glance. */
.fondwave-card label.aqhi-low {{
  background-color: #4CAF50; color: #FFFFFF; font-weight: 800;
  border-radius: 999px; padding: 2px 10px;
}}
.fondwave-card label.aqhi-moderate {{
  background-color: #FBC02D; color: {NIGHT_INDIGO}; font-weight: 800;
  border-radius: 999px; padding: 2px 10px;
}}
.fondwave-card label.aqhi-high {{
  background-color: #F57C00; color: #FFFFFF; font-weight: 800;
  border-radius: 999px; padding: 2px 10px;
}}
.fondwave-card label.aqhi-very-high {{
  background-color: #B71C1C; color: #FFFFFF; font-weight: 800;
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

.fondwave-terminal, .fondwave-terminal textview, .fondwave-terminal textview text {{
  background-color: {TERMINAL_BG};
  color: {TERMINAL_FG};
}}
.fondwave-terminal textview text selection {{
  background-color: {TERMINAL_FG};
  color: {TERMINAL_BG};
}}
"""


def apply():
    provider = Gtk.CssProvider()
    provider.load_from_string(FONDWAVE_CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
