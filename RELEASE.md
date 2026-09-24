# Zarya v0.17.1 "True Face"

**Released:** 2026-09-24

## What's new

- **Fixed:** the System/Backups/Updates status cards had no visible
  background or border at all when everything was fine — just text
  floating in space, only looking like an actual card once colored amber
  or red for a problem. They now look like a real card at all times; only
  the color changes when something needs attention.
- **Fixed:** in the maximized wide layout (v0.17.0), the status-card
  column was stretching to fill most of the window's width instead of
  staying a narrow column next to Today's Events.

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
