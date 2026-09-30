# Zarya v0.20.2 "Snug Fit"

**Released:** 2026-09-30

## What's new

- **Zarya works on smaller screens.** Maximizing on a smaller monitor no
  longer hides the To-Do/Habits sidebar or cuts off the right-hand cards; a
  sidebar width saved on a bigger screen can't push it out of view.
- **No more big vertical gap** between the status-card rows, and the
  side-by-side layout now waits until the window is wide enough (1500px) to
  give the cards room.

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
