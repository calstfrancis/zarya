# Zarya v0.12.3 "True Ledger"

**Released:** 2026-09-09

## What's new

Straight follow-up to yesterday's fix, from a direct question about how
retries interact with the run history:

- **A fully-failed automatic daily update now shows up in Recent Runs and
  sends a notification.** Previously, if the daily timer's own retries
  (added in 0.12.2) genuinely exhausted and today's update never actually
  succeeded, that failure was silently invisible on the main dashboard —
  no failure dot, no notification, "Run Now" gave no hint anything was
  wrong. The only place it showed at all was Preferences > Updates'
  status text.
- A retry still *in progress* is correctly distinguished from a *settled*
  failure (checked via the service's own active state), so this never
  double-counts — two failed attempts followed by a successful third one
  still shows as exactly one success, never two pointless failures. A
  fully exhausted failure is recorded at most once per day, and correctly
  leaves "Run Now" available rather than flipping it to "Run Anyway",
  since nothing actually succeeded.

See [CHANGELOG.md](CHANGELOG.md) for everything since earlier releases,
including v0.12.2 "True North" (fixed the daily timer failing right after
waking from suspend) and v0.12.1 "Steady Hours" (weather table now shows
±12 hours around now).

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

Already installed? `flatpak update` picks this up — no unit-file changes
this time, so no need to click "Reinstall" in Preferences > Updates.

## Running

```bash
flatpak run io.github.calstfrancis.zarya
```

---

## Full changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete history.
