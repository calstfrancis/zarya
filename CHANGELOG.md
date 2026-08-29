# Changelog

## [0.6.0] "Gathered Dawn" — multiple Google calendars

- Today's Events now supports multiple Google calendars — Preferences >
  Google lists every calendar on your account (checkboxes, fetched live),
  and you can select any combination. Defaults to just your primary
  calendar. A calendar that fails to fetch (removed, unshared) is skipped
  rather than failing the whole section.

## [0.5.0] "Coral Sync" — to-do sidebar synced with Google Tasks

- The to-do sidebar is now synced with Google Tasks instead of stored
  locally — add/check-off/remove all go through the real Google Tasks API
  (`@default` list), so it shows up in the Google Tasks app and Gmail too.
  One Google connection now covers both Calendar and Tasks (widened OAuth
  scope, single consent). Preferences' "Calendar" page is renamed "Google";
  the connect button now reads "Connect Google Account".
  **Needs the Tasks API enabled on the Google Cloud project (same step as
  Calendar was) and the `tasks` scope added to the consent screen** —
  external action, not something this commit can do. Anyone already
  connected needs to disconnect and reconnect once to pick up the wider
  scope; the old token doesn't cover Tasks calls and they'll fail until then.

## [0.4.0] "Quiet Ember" — system tray icon, hourly weather refresh

- Added a real system tray icon, talking directly to the StatusNotifierItem/
  StatusNotifierWatcher D-Bus protocol (the actual mechanism underneath
  libappindicator — no new library or flatpak module needed; verified it
  registers with the real KDE watcher before wiring it into the app).
  Launching from the autostart entry now starts hidden in the tray (a new
  `--background` flag) instead of always popping a window open — closing
  the window (or the new "Hide to Tray" button, renamed from "Close") hides
  it rather than quitting; a "Quit Zarya" menu item actually exits. Click
  the tray icon to show/hide the window. Degrades gracefully to normal
  window behavior on desktops with no tray watcher running.
- Weather (including alerts and AQHI) now auto-refreshes every hour, not
  just on open/manual refresh.

## [0.3.0] "Amber Watch" — weather alerts, AQHI, a real Cancel fix

- Added Environment Canada weather alerts to the Weather panel — active
  warnings/watches/statements near your location show as a colored banner
  (amber for yellow/orange risk, red for red risk) with the full alert text
  as a tooltip. Uses ECCC's MSC GeoMet OGC API (`api.weather.gc.ca`,
  `weather-alerts` collection), queried by a small bbox around your
  geocoded location. Canada-only by nature of the data source; silently
  shows nothing outside Canada rather than erroring.
- Added the current Air Quality Health Index (AQHI) next to the weather
  panel, from the same ECCC API (`aqhi-stations` + `aqhi-observations-realtime`
  collections) — finds the nearest monitoring station to your location and
  shows its latest reading with Canada's official Low/Moderate/High/Very
  High categories.
- To-do sidebar now uses the same Fondwave Konsole styling as the update
  log (cream/plum), not the dark gradient card — reads better as a
  persistent panel.
- Fixed a real bug in the Cancel button: it sent SIGKILL
  (`Gio.Subprocess.force_exit()`), which can never be caught — so it only
  killed the local `flatpak-spawn` wrapper, leaving the actual host-side
  `pkexec`/zypper/flatpak process orphaned and still running, which could
  hold the zypper lock for a subsequent "Run Anyway". Cancel now sends
  SIGTERM first (catchable, so flatpak-spawn and pkexec both forward it to
  the real process), falling back to a force-kill only if it's still
  running 5 seconds later.

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
