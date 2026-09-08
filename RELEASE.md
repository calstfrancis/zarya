# Zarya v0.12.0 "Silent Dawn"

**Released:** 2026-09-08

## What's new

The automatic daily update no longer pops a password prompt:

- **Preferences > Updates > Enable** sets up passwordless daily updates with
  a single password prompt, right in the app — no terminal, no separate
  script to find and run. It installs a root-owned systemd timer that runs
  `zypper` + the system flatpak update on its own daily schedule from then
  on, catching up automatically if the machine was asleep at the scheduled
  time. Click **Disable** in the same place to remove it.
- **"Run Now" is deliberately unchanged** — it still prompts for your
  password every time, exactly as before. This only removes the prompt
  from the unattended background case; a manual click is something you're
  present for anyway, so there was never a reason to touch that path.
- Nothing here grants any broader password-free access — no polkit rule of
  any kind is installed. Root's own timer needs none to run its own unit,
  and manual updates still go through the normal password prompt.

See [CHANGELOG.md](CHANGELOG.md) for everything since earlier releases,
including v0.11.1 "Steady Link" (fixed the "Open Pereprava" button doing
nothing on a flatpak install) and v0.11.0 "Clear Signal" (autostart on by
default, a beautified What's New window, fixed System Health icons).

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
