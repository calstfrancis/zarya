# Zarya v0.21.2 "Quiet Dawn"

**Released:** 2026-10-03

## What's new

- **No more morning password prompt.** If you've enabled the daily update
  timer in Preferences > Updates, opening Zarya (or logging in with
  autostart) now just records what the timer did instead of asking for
  your password. Without the timer, the automatic daily run still asks
  once, as before. "Run Now" always prompts.

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
