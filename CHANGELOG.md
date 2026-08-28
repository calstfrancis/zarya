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
- Added a Today's Events section, backed by Google Calendar (not CalDAV —
  Google dropped app-password CalDAV access). Uses an OAuth2 loopback flow
  (PKCE, no client secret exposed in the redirect) via Preferences > Calendar
  > "Connect Google Calendar"; only a read-only refresh token is stored, in
  the system keyring, never the password itself.
- Replaced the hourly weather line chart with a plain numbers table (hour /
  temp / humidity / rain %, current hour highlighted) — the line chart
  looked nice but wasn't actually usable at a glance.
- Weather, Backups, and Today's Events are now collapsible sections (click
  the header to fold/unfold, state persisted), each with a status icon in
  the header: a check if everything's fine, an error mark if a fetch failed
  or (for Backups) any job's last run failed.
- Filled in the real Google OAuth client ID/secret — "Connect Google
  Calendar" in Preferences is now functional. Repo made public at Cal's
  request; privacy policy and terms of service published at
  calstfrancis.github.io/privacy.html and /terms.html for the OAuth consent
  screen.
- Added a first-run onboarding wizard: city (weather, Celsius by default)
  and an optional Google Calendar connect step, skippable, shown once.
- Default temperature unit changed from Fahrenheit to Celsius.
- Weather section now uses Fondwave (dusk palette) styling — a deliberately
  branded gradient card, not a general theme change; everything else still
  routes through libadwaita's system colors.
- Redesigned the app icon as a synthwave sunset in Fondwave colors (sliced
  sun, perspective grid) to match.
- Backups section now has a button to open Pereprava directly (via
  flatpak-spawn --host, same mechanism as the update/backup-status calls).
- Fixed: `flatpak update -y` failed with "Deploy not allowed for user" —
  it updates both user and system-wide flatpak installs, but the system
  ones need privilege the same way zypper does, and there was no way to
  satisfy that running as a normal user. System flatpak updates are now
  folded into the same pkexec-privileged step as zypper
  (`flatpak update --system -y`); the unprivileged step now only runs
  `flatpak update --user -y`.
