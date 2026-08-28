# Changelog

## [0.2.0] — dev

- Renamed "Today's Events" to "Today's Events & Due Dates".
- Weather panel now shows current temperature and "feels like" (Open-Meteo's
  apparent temperature — accounts for wind and humidity year-round, so no
  separate summer-only humidex figure needed) at the top right.
- Weather's hourly table now has a frozen left label column (Hour/Temp/
  Humidity/Rain stay visible while scrolling), scrolls horizontally on a
  plain mouse wheel (no Shift needed), and auto-centers on the current hour
  whenever it loads or refreshes.
- The update log is now its own collapsible section, like Weather/Backups/
  Events.
- Added a persistent to-do sidebar (right side), Fondwave-styled, with a
  simple add/check-off/remove list stored in config.
- Added a desktop notification when an update finishes, success or failure.
- Added a run-history strip (last 14 runs, colored dots with date tooltips)
  next to the success/failure status row.
- Added a best-effort summary line ("zypper: N upgraded, M new · flatpak: K
  updated") parsed from the update output.
- Backups section now shows each job's next scheduled run alongside its last
  run.
- Added a "Preview" button that dry-runs `zypper dup` so you can see what
  would change before committing to a real run.
- Added a "What's New" panel (hamburger menu) that renders `CHANGELOG.md`
  live, matching the convention used by Zerkalo/Rubric/etc.
- Fixed a real crash: `keyring.py` let a `GLib.Error` from the Secret
  Service escape uncaught whenever it wasn't reachable (not running yet,
  still locked, timing during startup) — a lookup at window construction
  time could crash the whole app on launch. All keyring calls now handle
  this gracefully (lookup returns `None`, store/clear raise a catchable
  `KeyringError`) instead of propagating the raw D-Bus error. Found via a
  headless smoke test, not just inferred.

### Polish

- Fixed: the current-temp/feels-like label wasn't cleared when the location
  was blank, so it could show stale data after clearing your city.
- Weather table numbers now use tabular figures so columns stay aligned
  instead of wobbling with proportional-width digits.
- Backups and Today's Events rows now pair every colored status with an
  icon, not color alone (matches the accessibility commitments already
  published on calstfrancis.github.io).
- Changing only the temperature unit in Preferences no longer refetches
  weather over the network — it re-renders the already-cached data.
- To-do sidebar: empty state ("No tasks yet"), and a tooltip on the
  checkbox.
- Preview button now has an icon; About window has a tagline and copyright;
  the run-history dots have a "Recent runs:" label instead of being an
  unlabeled row of dots, and the whole row hides itself until there's
  history to show.

## [0.1.0] "Coral Dawn" — first release: daily update runner with weather, backups, and calendar

### Added
- Runs `zypper ref && zypper dup` and `flatpak update` (both user and system-wide installs) with a single graphical `pkexec` password prompt, live output in a window, and a Cancel button.
- Skips re-running if already updated today, with a persistent success/failure status row (survives restarts).
- Optional "Start at login" toggle (writes a plain XDG autostart entry).
- First-run onboarding wizard: set your city and optionally connect Google Calendar, both skippable, shown once.
- Daily weather report (Open-Meteo, no API key) as an hourly numbers table — temperature, humidity, rain % — in a Fondwave-styled card, °C by default.
- Backups section reading Pereprava's job status via `systemctl --user` (through `flatpak-spawn --host`), with a button to open Pereprava directly.
- Today's Events section backed by Google Calendar — OAuth2 with PKCE, only a read-only refresh token stored, in the system keyring.
- Weather, Backups, and Today's Events are collapsible sections, each with a status icon reflecting whether the last fetch (or, for Backups, every job) succeeded or failed.
- Update log styled with the Fondwave Konsole colorscheme (reproduced in CSS, no dependency on that profile being installed), sized to be readable by default.
- Synthwave sunset app icon in Fondwave colors.

### Fixed
- The update run no longer hangs between the zypper and flatpak steps — completion is now keyed on the subprocess actually exiting, not on its stdout pipe reaching EOF, which zypper/rpm could leave open indefinitely via a forked helper.
- `flatpak update` no longer fails on system-wide installs with "Deploy not allowed for user" — the system-flatpak update now runs inside the same privileged `pkexec` step as zypper, since it needs the same authority.
