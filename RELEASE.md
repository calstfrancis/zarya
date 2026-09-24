# Zarya v0.16.0 "Clear Deck"

**Released:** 2026-09-24

## What's new

A full pass on the main window's layout and information order, following a
UI/UX review against real (unmaximized) screenshots — the way the app
actually gets used day to day.

- **System Health, Backups, and Disk Growth are now three compact status
  cards** (System, Backups, Updates) in a single row, instead of several
  always-expanded sections stacked down the page. A card stays quiet until
  something actually needs attention — then it turns amber or red with a
  one-line detail. Click a card for the full detail.
- **The bottom button row is gone.** "Start at login" moved to
  Preferences > Updates; Run Now, the run history, and the Update Log moved
  into the Updates card. Closing the window still just hides it to the
  tray.
- **Habits moved into the sidebar**, right below To-Do.
- **The window title now shows today's date and a one-line status** — "Good
  afternoon · Toronto · all clear", or how many things need attention — and
  a single refresh button in the header replaced each section's own.
- **Fixed:** the hourly weather strip could silently fail to scroll to
  "now" on first launch and stay at its oldest hours instead.
- Today's Events now shows a "now" divider, dims events that have already
  ended, and gives each event a color dot for which calendar it's from. The
  weather card hides its Rain row entirely on a day with no rain forecast.
  Completed to-dos collapse under a "Completed (N)" toggle, and delete
  buttons on to-dos/habits only show on hover.

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
