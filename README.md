# Zarya

A small GTK4/libadwaita morning dashboard: it runs your system updates
(`zypper ref && zypper dup` and `flatpak update`), then shows the day's
weather, your backup status, and today's calendar events — all in one window.

- The automatic daily update runs with no password prompt at all, once you
  click Enable in Preferences > Updates (one password prompt, no terminal) —
  see [Passwordless daily updates](#passwordless-daily-updates) below.
  "Run Now" always prompts via `pkexec`, same as ever — that's unchanged on
  purpose.
- Skips re-running if it already updated today; persistent success/failure status
- Optional "Start at login" toggle
- Daily weather report (Open-Meteo, no API key) as an hourly temperature/
  humidity/rain table, styled with the Fondwave palette
- Backup status read from [Pereprava](https://github.com/calstfrancis/pereprava)'s
  rclone/rsync jobs, with a button to open it directly
- System Health: disk space and drive SMART status (via UDisks2, no root
  needed to read it)
- Today's Google Calendar events, and a persistent to-do sidebar synced with
  Google Tasks — one OAuth2 + PKCE connection covers both; only a refresh
  token is stored, in the system keyring
- A real system tray icon (StatusNotifierItem); autostart runs quietly in
  the background instead of opening a window
- First-run onboarding wizard for city and Google Account setup

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

## Passwordless daily updates

By default, the automatic daily update prompts for your password via
`pkexec`, same as a manual run — which defeats the point of it being
automatic. To fix just that: open **Preferences > Updates** and click
**Enable**. One password prompt, right there in the app — no terminal, no
separate script to go find and run.

This installs a root-owned systemd timer that runs the update on its own
daily schedule from then on — no app involvement, no password, and no
polkit rule of any kind, since root's own timer needs none to run its own
unit. "Run Now" in the app is deliberately **unchanged** and still prompts
via `pkexec` — this only removes the prompt from the unattended background
case, not from a manual click. Click **Disable** in the same place to
reverse it. See `zarya/CLAUDE.md`'s "Passwordless daily updates" section
for the full design.

## Privacy & Terms

- [Privacy Policy](https://calstfrancis.github.io/privacy.html)
- [Terms of Service](https://calstfrancis.github.io/terms.html)
