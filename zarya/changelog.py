import importlib.resources
import re
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk


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


_HEADING_RE = re.compile(r'^\[(?P<version>[^\]]+)\]\s*(?:"(?P<name>[^"]+)"\s*)?(?:—\s*(?P<desc>.*))?$')


def _parse_entries(text):
    """Group the changelog into (version, name, desc, [bullet, ...]) entries.

    A bullet's markdown continuation lines (indented, no leading "- ") are
    folded into the same paragraph rather than kept as separate lines — the
    raw file hand-wraps prose at ~78 columns, which isn't a real line break.
    """
    entries = []
    bullets = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            m = _HEADING_RE.match(line[3:].strip())
            if m:
                entries.append({
                    "version": m.group("version"),
                    "name": m.group("name"),
                    "desc": m.group("desc") or "",
                    "bullets": [],
                })
            else:
                entries.append({"version": line[3:].strip(), "name": None, "desc": "", "bullets": []})
            bullets = entries[-1]["bullets"]
            continue
        if not entries:
            continue
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
        elif stripped and bullets:
            bullets[-1] = f"{bullets[-1]} {stripped}"
    return entries


_BOLD_OR_CODE_RE = re.compile(r"\*\*(.+?)\*\*|`(.+?)`")


def _wrapping_text(text, css_classes=()):
    """A read-only, non-scrolling text widget that actually wraps to its
    allocated width, instead of Gtk.Label — whose reported minimum width
    for wrappable text equals its full unwrapped width, so any Label nested
    inside a scrolling ancestor (as every changelog entry is here) forces
    that ancestor, and the window itself, to grow to fit the longest bullet
    unwrapped rather than wrapping it. Gtk.TextView doesn't have this
    problem: it always wraps to whatever width it's given. Confirmed by
    screenshot — Gtk.Label blew the window out to ~2400px on this
    changelog's actual bullet text; Gtk.TextView held the window's set
    width and wrapped correctly."""
    tv = Gtk.TextView(
        editable=False, cursor_visible=False, hexpand=True,
        wrap_mode=Gtk.WrapMode.WORD_CHAR,
    )
    tv.add_css_class("changelog-text")
    for css_class in css_classes:
        tv.add_css_class(css_class)
    buf = tv.get_buffer()
    bold_tag = buf.create_tag("bold", weight=700)
    code_tag = buf.create_tag("code", family="monospace")

    pos = 0
    it = buf.get_end_iter()
    for m in _BOLD_OR_CODE_RE.finditer(text):
        if m.start() > pos:
            buf.insert(it, text[pos:m.start()])
        if m.group(1) is not None:
            buf.insert_with_tags(it, m.group(1), bold_tag)
        else:
            buf.insert_with_tags(it, m.group(2), code_tag)
        pos = m.end()
    if pos < len(text):
        buf.insert(it, text[pos:])

    # GtkTextView computes a height of 0 the first time it's measured,
    # before it's actually realized and has a Pango context to lay the
    # buffer out with — and nothing re-measures it afterwards on its own,
    # so it's permanently allocated zero height inside a non-expanding Box.
    # Queuing a resize once the main loop is next idle (i.e. once this
    # window has actually been presented and realized) forces the correct
    # wrapped height to be computed and used.
    GLib.idle_add(lambda: (tv.queue_resize(), False)[1])
    return tv


def _bullet_row(text, first, last):
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.add_css_class("fond-card")
    if first:
        row.add_css_class("fond-card-first")
    if last:
        row.add_css_class("fond-card-last")
    row.set_margin_start(2)
    row.set_margin_end(2)
    row.set_margin_top(8)
    row.set_margin_bottom(8)

    dot = Gtk.Label(label="•", valign=Gtk.Align.START)
    dot.add_css_class("dim-label")
    dot.set_margin_start(10)
    row.append(dot)

    body = _wrapping_text(text)
    body.set_margin_end(10)
    row.append(body)
    return row


def build_view(current_version):
    """A native widget tree for the changelog, styled per fond.css
    conventions (fond-section for each release, fond-card for its bullets)
    instead of one big Pango-markup label."""
    text = load_text()
    entries = _parse_entries(text)

    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    body.set_margin_top(4)
    body.set_margin_bottom(20)
    body.set_margin_start(4)
    body.set_margin_end(4)

    for i, entry in enumerate(entries):
        heading_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        heading_row.add_css_class("fond-section")
        heading_row.set_margin_top(0 if i == 0 else 22)

        dot = Gtk.Label(label="●")
        dot.add_css_class("fond-section-dot")
        dot.add_css_class("dim-label")
        heading_row.append(dot)

        ver_label = Gtk.Label(label=entry["version"])
        ver_label.add_css_class("fond-section-title")
        heading_row.append(ver_label)

        if entry["version"] == current_version:
            badge = Gtk.Label(label="Current")
            badge.add_css_class("fond-section-meta")
            badge.add_css_class("accent")
            heading_row.append(badge)

        body.append(heading_row)

        title_text = entry["name"] or entry["desc"]
        subtitle_text = entry["desc"] if entry["name"] else ""
        if title_text:
            title = _wrapping_text(title_text, css_classes=("title-3",))
            title.set_margin_top(2)
            body.append(title)
        if subtitle_text:
            subtitle = _wrapping_text(subtitle_text, css_classes=("dim-label",))
            body.append(subtitle)

        n = len(entry["bullets"])
        for j, bullet in enumerate(entry["bullets"]):
            body.append(_bullet_row(bullet, j == 0, j == n - 1))

    return body
