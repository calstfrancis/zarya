# Zarya v0.20.0 "Clear Horizon"

**Released:** 2026-09-29

## What's new

- **The hourly forecast looks forward.** It starts at "Now" and runs 24
  hours ahead; past hours are gone. Midnight columns show the weekday.
- **A Wind row** (km/h, or mph with Fahrenheit units) joins the hourly table.
- **Fixed:** the System card's summary overran the card in an unmaximized
  window. Each reading now sits on its own line.

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
