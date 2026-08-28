# Zarya

A small GTK4/libadwaita morning dashboard: it runs your system updates
(`zypper ref && zypper dup` and `flatpak update`), then shows the day's
weather, your backup status, and today's calendar events — all in one window.

- Single graphical password prompt (via `pkexec`) for the whole privileged step
- Skips re-running if it already updated today; persistent success/failure status
- Optional "Start at login" toggle
- Daily weather report (Open-Meteo, no API key) as an hourly temperature/
  humidity/rain table, styled with the Fondwave palette
- Backup status read from [Pereprava](https://github.com/calstfrancis/pereprava)'s
  rclone/rsync jobs, with a button to open it directly
- Today's Google Calendar events (OAuth2 + PKCE; only a read-only refresh
  token is stored, in the system keyring)
- First-run onboarding wizard for city and calendar setup

Zarya runs host `zypper`/`flatpak`/`systemctl` commands via `flatpak-spawn --host`
— it needs to manage the host system, so the flatpak sandbox is intentionally
loose here (see the project's root `CLAUDE.md` note on Pereprava for the same
tradeoff).

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

First launch walks through a short onboarding wizard (city, optional Google
Calendar connect). Toggle "Start at login" in the window to have it run
automatically each day.

## Privacy & Terms

- [Privacy Policy](https://calstfrancis.github.io/privacy.html)
- [Terms of Service](https://calstfrancis.github.io/terms.html)
