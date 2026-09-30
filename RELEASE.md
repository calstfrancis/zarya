# Zarya v0.21.0 "Small Hours"

**Released:** 2026-09-30

## What's new

- **Coming up card.** The sidebar now shows what's on right now (with time
  left), the next event with a live countdown, and a rain-soon line from the
  hourly forecast.
- **Compact mode.** One button in the header bar shrinks Zarya to a slim
  single column with the weather, Coming up and status cards. Press it again
  to return to your previous window size.
- **Even status cards** that no longer clip their last line, and a tidier
  sunrise/sunset block in the weather header.

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
