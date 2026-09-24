# Zarya v0.17.3 "Three Up"

**Released:** 2026-09-24

## What's new

- **Fixed:** the maximized wide layout still read as two columns (Today's
  Events, one wide status strip) plus the sidebar — not the three columns
  the layout was designed around. The status area is now a genuine
  2-column grid: System and Backups side by side, Updates spanning the
  full width below them. Today's Events and the status area now split the
  available width evenly, instead of Events claiming most of it.

See [CHANGELOG.md](CHANGELOG.md) for everything since earlier releases.

## Download

| Method | Platform |
|---|---|
| Flatpak (`calstfrancis` repo) | Any Linux with Flatpak installed |

## Installation

```bash
flatpak remote-add --user calstfrancis \
  https://calstfrancis.github.io/flatpak/calstfrancis.flatpakrepo
flatpak install calstfrancis io.github.calstfrancis.zarya
```

Already installed? `flatpak update` picks this up, and Zarya will offer to
restart itself once it does.

## Running

```bash
flatpak run io.github.calstfrancis.zarya
```

---

## Full changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete history.
