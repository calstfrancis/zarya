# Changelog

## [0.10.1] "dev" — fix autorun not firing, unscrollable window on small screens

- Fixed: the daily auto-run (via "Start at login") wasn't actually firing.
  Two causes: (1) the on-disk autostart entry could go stale — it's only
  (re)written when the switch is toggled, so a file created before the
  `--background` flag existed (v0.4.0) kept launching without it; the app
  now re-syncs the entry to the current template on every startup if the
  switch is on. (2) The autostart entry only runs at an actual login, but
  this machine (and presumably others) mostly suspends/resumes rather than
  logging out daily — so on every day between real logins/reboots, nothing
  ever re-triggered the run. Zarya now also polls every 5 minutes while
  running and auto-runs if the day has rolled over and it hasn't updated
  yet, independent of login.
- Fixed: on a small/low-res screen (e.g. a T490's display), the main
  content didn't fit and the bottom "Run Now"/"Cancel"/"Hide to Tray" row
  could end up below the bottom of the screen with no way to reach it. The
  dashboard content now scrolls in its own `Gtk.ScrolledWindow`, and the
  action row (plus "Start at login") is a persistent bottom bar via
  `Adw.ToolbarView.add_bottom_bar`, always visible regardless of window
  height. Verified headlessly at a 1366×700 window size before and after.

## [0.10.0] "Cool Dawn" — CPU/GPU thermal health, flatpak-system retry

- Added CPU/GPU temperature to System Health, same treatment as disk/drive/
  battery: reads hwmon sensors via `flatpak-spawn --host` (allowlisted to
  actual CPU/GPU chips — k10temp/coretemp/zenpower, amdgpu/nouveau/i915/xe
  — skipping NVMe/battery/Wi-Fi/AC sensors hwmon also exposes). Verified
  against this machine's real sensors (k10temp/Tctl, amdgpu/edge) before
  wiring it in.
- Fixed (best-effort): the system flatpak update occasionally failing right
  after zypper succeeds, which looked like the pkexec/polkit authorization
  going stale by the time control reached that step. The privileged step
  now emits a hidden progress marker after zypper finishes (filtered out of
  the visible log); if the overall step fails but the marker was seen, the
  system flatpak update alone is retried once with a fresh pkexec call
  before giving up, keeping the single-prompt UX for the common case.

## [0.9.2] "Clear Order" — dashboard reorder, remove Preview

- Reordered the dashboard: Weather is now first, followed by Today's
  Events & Due Dates, System Health, Backups, then the "already updated
  today" status area moved down to sit directly above the Update Log
  (previously at the very top).
- Removed the Preview (dry-run) button.

## [0.9.1] "True Reading" — fix the AQI number itself

- Fixed: the "AQI" badge was actually showing Canada's AQHI (a 1-10 health
  scale), not the standard AQI (0-500) that every other weather app shows
  and that a reading like "14 (Low)" is measured on — a value of "1" on the
  wrong scale looked plausible but meant something completely different.
  `weather_aqhi.py` → `weather_aqi.py`, now sourced from Open-Meteo's
  air-quality API (`us_aqi`), which also works globally instead of being
  Canada-only. Badge now reads e.g. "AQI 59 (Moderate)" with the correct
  six-tier EPA color scale (green/yellow/orange/red/purple/maroon).
  Verified against live data before and after the change.

## [0.9.0] "Vivid Dawn" — HTML-entity fix, resizable sidebar, AQI badge

- Fixed: event/task titles with apostrophes (and other special characters)
  showed as literal HTML entities, e.g. "Emma&#39;s Mom's Birthday" instead
  of "Emma's Mom's Birthday" — Google's Calendar and Tasks APIs return
  HTML-escaped text in some fields; now decoded via `html.unescape()`.
- The to-do sidebar is now resizable — a draggable divider (`Gtk.Paned`)
  instead of a fixed width, position persisted to config (debounced, same
  pattern as Zerkalo's pane-position handling).
- The current-hour column in the weather table is now a filled pill, not
  just bold text — stands out at a glance instead of blending in.
- Air quality is now a real color-coded badge (green/yellow/orange/red per
  AQHI tier) instead of plain colored text.

## [0.8.0] "Steady Charge" — battery health

- Added battery health to the System Health section, same treatment as
  drive SMART status: reads UPower's `Capacity` property (already the
  wear/health percentage — verified it matches EnergyFull/EnergyFullDesign
  exactly, no need to compute it) plus charge level and cycle count, over
  the system D-Bus, no root needed. Skipped entirely (not an error) on
  desktops with no battery. Verified against this machine's real battery.
- Fixed: the About window and `pyproject.toml` attributed the app to
  "Praxis" (a stale template placeholder) instead of Cal — now says
  "calstfrancis" throughout.

## [0.7.0] "Steel Dawn" — System Health section (disk space + SMART)

- Added a System Health section (next to Backups): disk space for each real
  mounted filesystem (via the same flatpak-spawn --host approach as
  everything else that needs host state — the sandbox's own "/" is the
  runtime image, not the host disk), and drive health via UDisks2's cached
  SMART properties over the system D-Bus. Deliberately doesn't shell out to
  `smartctl` — that needs root for raw device access, and prompting for a
  password just to display a health icon would be bad UX; UDisks2 (which
  already runs as root on the host) exposes the same cached SMART data
  read-only to any user. Handles both ATA (SmartFailing) and NVMe
  (SmartCriticalWarning) drives. Verified against this machine's real NVMe
  drive before considering it done, not just unit-tested.

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
