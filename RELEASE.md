# Zarya v0.21.1 "Steady Shelf"

**Released:** 2026-09-30

## What's new

- **Coming up moves to the top** of the sidebar, above To-Do.
- **The sidebar sizes itself.** It scales with the window (300-440px) until
  you drag it; after that your chosen width is kept at any window size
  without squeezing the content.
- **Short windows** no longer force the window taller; the sidebar scrolls.

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
