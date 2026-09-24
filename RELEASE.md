# Zarya v0.17.0 "Wide Deck"

**Released:** 2026-09-24

## What's new

- **Maximizing the window now uses the extra width** instead of stretching
  the same single column across it: Today's Events sits on the left, and
  the System/Backups/Updates status cards stack in a column on the right.
  The layout switches back automatically once the window narrows below
  about 1200px.

See [CHANGELOG.md](CHANGELOG.md) for everything since earlier releases,
including v0.16.0 "Clear Deck" (the status-card redesign, sidebar merge,
and bottom-bar removal this builds on).

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
