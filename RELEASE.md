# Zarya v0.15.0 "True Horizon"

**Released:** 2026-09-24

## What's new

- **Fixed: the weather card's gradient now actually lines up with today's
  real sunrise and sunset.** It previously assumed a fixed 12-hour day
  centered on clock-noon, so on a short winter day it stayed bright for
  hours after the sun had actually set (and started brightening too early
  in the morning). It's now a smooth arc between today's *real* sunrise and
  sunset — dark outside that window, brightest exactly at solar noon inside
  it — so it matches the actual hours of daylight and dark year-round.
- **A day-length delta** ("+Nm daylight" / "−Nm daylight") now shows next
  to sunrise/sunset, comparing today against yesterday.
- **A subtle rain or snow tint** now appears over the weather gradient when
  it's currently precipitating, colored and scaled to intensity from the
  live weather conditions.

See [CHANGELOG.md](CHANGELOG.md) for everything since earlier releases,
including v0.14.0 "Lunar Reset" (restart-after-update prompt, moon phase,
weekly habit rollup).

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

Already installed? `flatpak update` picks this up — and Zarya will offer to
restart itself once it does.

## Running

```bash
flatpak run io.github.calstfrancis.zarya
```

---

## Full changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete history.
