# Zarya v0.13.0 "Amber Bloom"

**Released:** 2026-09-24

## What's new

- **Today's Events, System Health, and Backups now auto-refresh in the
  background** — every 15, 5, and 10 minutes respectively — instead of only
  updating when you click refresh or open the app.
- **The weather card now shows today's sunrise and sunset**, and its
  gradient shifts from its darkest colors at night to its lightest at solar
  noon and back — phased to the real sunrise/sunset midpoint once weather
  has loaded.
- **A new Disk Growth section** reports which top-level home directories
  have grown the most over the past week, once a week of history has been
  collected (it starts building that history from your first launch on this
  version).
- **A new Habits section** — a small daily habit tracker. Add a habit,
  click it to mark today done, and see your current streak. No account or
  external API involved; everything stays local.

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

Already installed? `flatpak update` picks this up.

## Running

```bash
flatpak run io.github.calstfrancis.zarya
```

---

## Full changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete history.
