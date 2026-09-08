# Zarya v0.12.1 "Steady Hours"

**Released:** 2026-09-08

## What's new

- **The hourly weather table now always shows the 12 hours before and 12
  hours after right now** (25 columns, centered on "now"), instead of a
  fixed midnight-to-midnight window that showed mostly-past hours late in
  the day and mostly-future hours early in the morning.
- **Fixed "Run Anyway" silently doing less than asked.** If the daily
  timer (Preferences > Updates) had already succeeded that day, clicking
  "Run Anyway" skipped straight to the unprivileged flatpak step instead
  of actually forcing a real re-run — it reused the same check meant only
  to spare a redundant password prompt on the day's *first* click, not to
  water down an explicit forced re-run into a no-op. An explicit "Run
  Anyway" now always forces a genuine re-run.

See [CHANGELOG.md](CHANGELOG.md) for everything since earlier releases,
including v0.12.0 "Silent Dawn" (passwordless daily updates, set up in
Preferences) and v0.11.1 "Steady Link" (fixed the "Open Pereprava" button).

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
