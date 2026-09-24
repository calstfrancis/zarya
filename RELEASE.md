# Zarya v0.18.0 "Full Picture"

**Released:** 2026-09-24

## What's new

- **Fixed:** the maximized wide layout's status-card area could overflow
  the window and push the sidebar off-screen (clipped To-Do text) once
  Today's Events and the status cards split the width evenly — a leftover
  fixed width on the card content, sized for when it only ever lived in a
  popover, was forcing the whole layout wider than the window.
- **Disk usage bars:** the System card now shows a visual bar under each
  drive's numbers, not just a percentage as text — colored amber/red at
  the same thresholds already used elsewhere.
- **Relative backup times:** last/next run times now read "12 h ago", "in
  11 h", "yesterday 14:32", or "last Tuesday" instead of a raw timestamp —
  hover for the exact time.
- **Plainer weather language:** sunrise/sunset now reads "Sunrise 7:03 AM
  · Sunset 7:07 PM" instead of a 24-hour range, and the day-length delta
  reads "3 min less daylight than yesterday" instead of "−3m daylight".

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
