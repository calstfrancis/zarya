# Zarya v0.20.1 "Full Shelf"

**Released:** 2026-09-29

## What's new

- **The System card shows every mounted disk.** It used to check only `/` and
  your home folder, so an extra drive (for example a SATA disk at `/mnt/data`)
  never appeared. Each real block-device filesystem is now listed, labelled
  by its mount folder; boot/EFI partitions and removable media are skipped.

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
