# Zarya v0.19.0 "True to Form"

**Released:** 2026-09-24

## What's new

A full, area-by-area pass matching the app against the mockup it was
originally built from.

- **The weather card is now a "hero" layout**: a large current temperature,
  condition, and feels-like/high/low on the left, sunrise/sunset/day-length/
  moon phase in a pill in the middle, and the AQI badge on the right —
  replacing the original two lines of small text.
- **The hourly table** now shows Hour/Temp/Rain/Humidity in that order,
  spells out hours ("1 PM" instead of "1p"), and the current hour's column
  simply reads "Now".
- **Disk Growth is now its own card** in a real 2x2 grid in the maximized
  layout (System/Backups on top, Updates/Disk Growth below), instead of
  folded into System with Updates spanning the full width.
- **System's drive/battery/temperature readings are now one summary line**
  ("2 drives healthy · CPU 58°C"), and disk usage uses friendly names
  ("System ( / )" / "Home") with a cleaner "{pct}% of {total}" format.
- **Backup rows are now two columns** — name, and one combined status like
  "12 h ago · next in 11 h" or "Running · 1 h 6 min" — instead of four.
- **Every status card's header now shows its state inline** next to the
  title in the wide layout, and the Updates card reports whether the
  passwordless daily timer is actually enabled.

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
