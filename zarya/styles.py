import gi

gi.require_version("Gtk", "4.0")

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
.fondwave-card scrollbar {{ opacity: 0.6; }}
"""


def apply():
    provider = Gtk.CssProvider()
    provider.load_from_string(FONDWAVE_CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
