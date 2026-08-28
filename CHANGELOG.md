# Changelog

## [0.1.0] — dev

- Initial version: runs `zypper ref && zypper dup` (single pkexec prompt) and
  `flatpak update`, with live output in a GTK4/libadwaita window.
- Skips re-running if already updated today; "Run Anyway" button to force it.
- Optional "Start at login" toggle that writes a plain XDG autostart entry.
- Fixed: the update run could hang forever between the zypper and flatpak
  steps — completion was gated on the subprocess's stdout pipe reaching EOF,
  but zypper/rpm can fork a helper (e.g. gpg-agent) that inherits the pipe
  and keeps it open after the actual command has already exited. Completion
  is now driven by the process itself exiting, not by the pipe closing.
- Added a Cancel button so a stuck or long-running step can be aborted.
- Added a daily weather report: hourly temperature, humidity, and
  precipitation-probability charts for a configurable location (Open-Meteo,
  no API key), with a hover crosshair and a °F/°C toggle.
- Moved weather location/units into a proper Preferences window, reachable
  from a hamburger menu in the header bar — fixes weather silently never
  showing anything, which turned out to be the inline location field only
  taking effect on Enter, with no visible confirmation that it had.
- Added a clear success/failure status row for the last update run (icon +
  colored label), persisted across restarts, not just shown during a run.
- Added a Backups section: reads Pereprava's job definitions and queries
  `systemctl --user` (via flatpak-spawn --host) for each job's last result.
- Added a Today's Events section: reads events directly from a CalDAV
  server (e.g. Disroot) via a calendar-query REPORT with server-side
  recurrence expansion; the app password is stored in the system keyring
  (libsecret/KWallet), not in plaintext config.
