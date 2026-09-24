# Zarya v0.17.2 "Open Book"

**Released:** 2026-09-24

## What's new

- **Fixed:** in the maximized wide layout, System/Backups/Updates still
  only showed the same one-line summary as the normal window. They now
  show each card's full detail directly inline — storage bars, the backup
  job list, the update log/history/Run Now button — with no click needed,
  matching the design this layout was built from. The normal (narrow)
  window is unchanged: cards there still show a one-line summary you click
  for the detail popover.

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
