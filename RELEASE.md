# Zarya v0.14.0 "Lunar Reset"

**Released:** 2026-09-24

## What's new

- **Zarya now offers to restart itself right after an update installs a new
  version of Zarya** — a small dialog with "Restart Now" / "Later". An
  already-running Zarya keeps executing its old code in memory until it's
  actually relaunched, so this closes that gap for both a manual "Run Now"
  and the silent daily background update.
- **Today's moon phase and illumination**, shown next to sunrise/sunset in
  the weather card — no extra network call, just a plain astronomical
  calculation.
- **Each habit row now shows a rolling "X/7 this week" count** alongside its
  streak.

See [CHANGELOG.md](CHANGELOG.md) for everything since earlier releases,
including v0.13.0 "Amber Bloom" (background auto-refresh, sunrise/sunset,
Disk Growth, Habits).

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

Already installed? `flatpak update` picks this up — and starting with this
release, Zarya will offer to restart itself once it does.

## Running

```bash
flatpak run io.github.calstfrancis.zarya
```

---

## Full changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete history.
