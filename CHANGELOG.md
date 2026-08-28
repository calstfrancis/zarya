# Changelog

## [0.3.0] — dev

- Added Environment Canada weather alerts to the Weather panel — active
  warnings/watches/statements near your location show as a colored banner
  (amber for yellow/orange risk, red for red risk) with the full alert text
  as a tooltip. Uses ECCC's MSC GeoMet OGC API (`api.weather.gc.ca`,
  `weather-alerts` collection), queried by a small bbox around your
  geocoded location. Canada-only by nature of the data source; silently
  shows nothing outside Canada rather than erroring.

## [0.2.0] "Amber Horizon" — weather polish, to-do sidebar, notifications

### Added
- Renamed "Today's Events" to "Today's Events & Due Dates".
- Weather panel shows current temperature and "feels like" (Open-Meteo's apparent temperature — covers wind chill and heat index year-round, no separate humidex needed) at the top right.
- Weather's hourly table has a frozen left label column (Hour/Temp/Humidity/Rain stay visible while scrolling), scrolls horizontally on a plain mouse wheel, and auto-centers on the current hour on every load/refresh. Numbers use tabular figures so columns stay aligned.
- The update log is now its own collapsible section, like Weather/Backups/Events.
- A persistent to-do sidebar (right side, Fondwave-styled): add/check-off/remove, saved to config, with an empty state and a tooltip on the checkbox.
- A desktop notification when an update finishes, success or failure.
- A run-history strip (last 14 runs, colored dots with date tooltips) labeled "Recent runs:", hidden until there's history to show.
- A best-effort summary line ("zypper: N upgraded, M new · flatpak: K updated") parsed from the update output.
- Backups section shows each job's next scheduled run alongside its last run, and every status now pairs a colored label with an icon — not color alone, matching the accessibility commitments already published on calstfrancis.github.io. Today's Events rows get the same icon treatment.
- A "Preview" button (with icon) that dry-runs `zypper dup` so you can see what would change before committing to a real run.
- A "What's New" panel (hamburger menu) that renders `CHANGELOG.md` live, matching the convention used by Zerkalo/Rubric/etc. About window gets a tagline and copyright.
- Preferences: changing only the temperature unit re-renders cached data instead of refetching over the network; only an actual location change triggers a refetch.

### Fixed
- A real crash: `keyring.py` let a `GLib.Error` from the Secret Service escape uncaught whenever it wasn't reachable (not running yet, still locked, timing during startup) — a lookup at window-construction time could crash the app on launch. All keyring calls now handle this gracefully. Found via a headless smoke test.
- The current-temp/feels-like label wasn't cleared when the location was blank, so it could show stale data after clearing your city.

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
