import importlib.resources
import re
from pathlib import Path

from gi.repository import GLib


def load_text():
    try:
        return importlib.resources.files("zarya.data").joinpath("CHANGELOG.md").read_text()
    except (FileNotFoundError, ModuleNotFoundError, NotADirectoryError):
        pass
    # Dev fallback (pip install -e .): the packaged copy under zarya/data/
    # only exists after a real build; read the repo-root file directly.
    candidate = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    if candidate.exists():
        return candidate.read_text()
    return "_Changelog not found._"


def to_pango_markup(text):
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            escaped = GLib.markup_escape_text(line[3:].strip())
            lines.append(f"\n<b><big>{escaped}</big></b>")
        elif line.startswith("### "):
            escaped = GLib.markup_escape_text(line[4:].strip())
            lines.append(f"\n<b>{escaped}</b>")
        elif line.startswith("- "):
            lines.append(f"  •  {_inline_markup(line[2:].strip())}")
        elif line.strip():
            lines.append(_inline_markup(line.strip()))
    return "\n".join(lines)


def _inline_markup(text):
    escaped = GLib.markup_escape_text(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<tt>\1</tt>", escaped)
    return escaped
