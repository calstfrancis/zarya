# Zarya v0.11.1 "Steady Link"

**Released:** 2026-09-08

## What's new

A small bug fix:

- **The "Open Pereprava" button (in the Backups section) did nothing** on a
  flatpak install of Pereprava. It launched `pereprava` via `flatpak-spawn
  --host`, but that command only exists on PATH for Pereprava's
  install-script distribution (`~/.local/bin`) — `flatpak-spawn --host`
  doesn't reliably see that directory, so the host command failed silently
  with no output for Zarya to report. It now launches via `flatpak run
  io.github.calstfrancis.pereprava` instead, which doesn't depend on PATH at
  all — the same way Zarya's own autostart entry already launches itself.

See [CHANGELOG.md](CHANGELOG.md) for everything since earlier releases,
including v0.11.0 "Clear Signal" (autostart on by default, a beautified
What's New window, fixed System Health icons) and the releases before that.

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
