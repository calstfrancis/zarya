# Release Notes

## [0.5.0] "Coral Sync" — to-do sidebar synced with Google Tasks

### Added

- The to-do sidebar is now backed by real Google Tasks (`@default` list)
  instead of local storage — add/check-off/remove all sync for real, and
  tasks show up in the Google Tasks app and Gmail too.
- One Google connection now covers both Calendar and Tasks — a single,
  widened-scope consent instead of two separate connect flows. Preferences'
  "Calendar" page is renamed "Google"; "Connect Google Calendar" is now
  "Connect Google Account".

### Requires external setup

- The Google Tasks API needs to be enabled on the Google Cloud project
  (console.cloud.google.com/apis/library/tasks.googleapis.com — not "Cloud
  Tasks API", a different, unrelated product), and the `tasks` scope added
  to the OAuth consent screen.
- Anyone already connected needs to disconnect and reconnect once in
  Preferences to pick up the wider scope — the old token doesn't cover
  Tasks calls.

## [0.4.0] "Quiet Ember" — system tray icon, hourly weather refresh

### Added

- A real system tray icon, talking directly to the StatusNotifierItem/
  StatusNotifierWatcher D-Bus protocol — the mechanism underneath
  libappindicator, with no new library or flatpak module needed. Degrades
  gracefully to normal window behavior if no tray watcher is running.
- Launching from the autostart entry (`--background`) now starts hidden in
  the tray and runs the update/fetches silently, instead of always opening
  a window at login. Closing the window ("Hide to Tray") hides it instead
  of quitting; a new "Quit Zarya" menu item is the real way to exit. Click
  the tray icon to show/hide the window.
- Weather (including alerts and AQHI) now auto-refreshes every hour.

## [0.3.0] "Amber Watch" — weather alerts, AQHI, a real Cancel fix

### Added

- Environment Canada weather alerts on the Weather panel — active
  warnings/watches/statements near your location as a colored banner
  (amber/red by risk), full text on hover. ECCC's MSC GeoMet OGC API,
  Canada-only, silently empty elsewhere.
- Current Air Quality Health Index (AQHI) next to the weather panel, from
  the nearest ECCC monitoring station.
- To-do sidebar now uses the Fondwave Konsole styling (cream/plum), matching
  the update log, instead of the dark gradient card.

### Fixed

- Cancel sent SIGKILL, which can't be caught — it only killed the local
  `flatpak-spawn` wrapper, leaving the real host-side zypper/flatpak process
  running and able to hold the zypper lock for a later run. Cancel now
  sends SIGTERM first (forwarded to the real process by flatpak-spawn and
  pkexec), force-killing only as a 5-second fallback.

## [0.2.0] "Amber Horizon" — weather polish, to-do sidebar, notifications

### Added

- Weather panel shows current temperature and "feels like" (Open-Meteo's
  apparent temperature — covers wind chill and heat index year-round) at the
  top right.
- Weather's hourly table has a frozen left label column, scrolls horizontally
  on a plain mouse wheel, and auto-centers on the current hour whenever it
  loads or refreshes. Numbers use tabular figures for clean alignment.
- The update log is now its own collapsible section.
- A persistent to-do sidebar (Fondwave-styled): add/check-off/remove, saved
  to config.
- A desktop notification when an update finishes, success or failure.
- A run-history strip (last 14 runs) and a best-effort update summary line
  parsed from zypper/flatpak output.
- Backups section shows each job's next scheduled run; every status now
  pairs a colored label with an icon, not color alone (Backups and Today's
  Events both) — matching the accessibility commitments published on
  calstfrancis.github.io.
- A "Preview" button that dry-runs `zypper dup`.
- A "What's New" panel (hamburger menu) rendering `CHANGELOG.md` live.
- "Today's Events" renamed to "Today's Events & Due Dates".

### Fixed

- A real crash: `keyring.py` let a `GLib.Error` from the Secret Service
  escape uncaught whenever it wasn't reachable — a lookup at
  window-construction time could crash the app on launch. Found via a
  headless smoke test.
- The current-temp/feels-like label wasn't cleared when the location was
  blank.

## [0.1.0] "Coral Dawn" — first release

A daily update runner (zypper + flatpak, one password prompt) that grew into
a small morning dashboard.

### Added

- Runs `zypper ref && zypper dup` and `flatpak update` (both user and
  system-wide installs) with a single graphical `pkexec` password prompt,
  live output in a window, and a Cancel button.
- Skips re-running if already updated today, with a persistent success/failure
  status row that survives restarts.
- Optional "Start at login" toggle (writes a plain XDG autostart entry).
- First-run onboarding wizard: set your city and optionally connect Google
  Calendar, both skippable, shown once.
- Daily weather report ([Open-Meteo](https://open-meteo.com/), no API key) as
  an hourly numbers table — temperature, humidity, rain % — in a card styled
  with the Fondwave palette, °C by default.
- Backups section reading [Pereprava](https://github.com/calstfrancis/pereprava)'s
  job status via `systemctl --user` (through `flatpak-spawn --host`), with a
  button to open Pereprava directly.
- Today's Events section backed by Google Calendar — OAuth2 with PKCE, only a
  read-only refresh token stored, in the system keyring.
- Weather, Backups, and Today's Events are collapsible sections, each with a
  status icon reflecting whether the last fetch (or, for Backups, every job)
  succeeded or failed.
- Update log styled with the Fondwave Konsole colorscheme (reproduced in CSS,
  no dependency on that profile being installed), sized to be readable by
  default.
- Synthwave sunset app icon in Fondwave colors.

### Fixed

- The update run no longer hangs between the zypper and flatpak steps —
  completion is now keyed on the subprocess actually exiting, not on its
  stdout pipe reaching EOF, which zypper/rpm could leave open indefinitely
  via a forked helper (e.g. gpg-agent).
- `flatpak update` no longer fails on system-wide installs with "Deploy not
  allowed for user" — the system-flatpak update now runs inside the same
  privileged `pkexec` step as zypper, since it needs the same authority.
