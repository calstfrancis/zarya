# Zarya

A small GTK4/libadwaita app that runs your system updates (`zypper ref && zypper dup`)
and `flatpak update`, first thing in the morning.

- Single graphical password prompt (via `pkexec`) for the zypper step
- Runs `flatpak update` too
- Shows live output in a window instead of a background silent job
- Skips re-running if it already updated today
- Optional "Start at login" toggle

Zarya runs host `zypper`/`flatpak` commands via `flatpak-spawn --host` — it needs
to manage the host system, so the flatpak sandbox is intentionally loose here
(see the project's root `CLAUDE.md` note on Pereprava for the same tradeoff).

## Install

```
flatpak remote-add --user calstfrancis \
  https://calstfrancis.github.io/flatpak/calstfrancis.flatpakrepo
flatpak install calstfrancis io.github.calstfrancis.zarya
```

## Run

```
flatpak run io.github.calstfrancis.zarya
```

Toggle "Start at login" in the window to have it run automatically each day.
