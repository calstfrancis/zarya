# Zarya v0.11.0 "Clear Signal"

**Released:** 2026-09-01

## What's new

Mostly polish on top of the recent System Health and autorun-reliability work:

- **"Start at login" now switches on automatically** the first time you finish
  setup, instead of defaulting off and requiring you to find and flip it
  yourself — Zarya's whole point is the daily unattended run, so it now
  works out of the box.
- **Fixed a broken-image icon** on the CPU/GPU temperature rows in System
  Health — `temperature-symbolic` isn't a real icon in Adwaita's icon set,
  so it showed a box-with-a-red-circle instead of a status icon. Swapped for
  the same checkmark already used for a healthy drive.
- **Simpler System Health labels** — dropped the hwmon chip name from
  CPU/GPU rows (just "CPU — 62°C" instead of "CPU (k10temp) — 62°C") and
  the device model from the battery row (just "Battery — 87% charged"),
  matching the system tray's convention of leading with what the reading is
  for, not the hardware it came from.
- **Rebuilt the What's New window** as native widgets styled to the Fond
  suite's shared `fond.css` conventions (a card per release, a "Current"
  badge for the installed version) instead of one long block of Pango-markup
  text — matching Zerkalo's changelog window.

See [CHANGELOG.md](CHANGELOG.md) for everything since earlier releases,
including v0.10.1 "Faithful Dawn" (reliable autorun, a scrollable window for
small screens), v0.10.0 "Cool Dawn" (CPU/GPU temperature in System Health),
and the releases before that — weather alerts and AQI, a system tray icon,
battery/drive health, multi-calendar support, and Google Tasks sync.

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

Already installed? `flatpak update` picks this up.

## Running

```bash
flatpak run io.github.calstfrancis.zarya
```

---

## Full changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete history.
