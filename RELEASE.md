# Zarya v0.20.3 "Flex Room"

**Released:** 2026-09-30

## What's new

- **Panes resize to fit.** The left edge of the content (weather, Events) is
  no longer cut off at wide window sizes; the content/sidebar split now
  always leaves the content the room it needs and the sidebar at least 300px.
- **Long backup names truncate** instead of forcing the cards wider than the
  window, and the status cards now use the extra width in the wide layout.
- **Forecast labels line up** with their values in the hourly strip.

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
