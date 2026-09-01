# Zarya — Developer Notes

## What it is

A GTK4/libadwaita morning dashboard, flatpak-packaged. Core job: run
`zypper ref && zypper dup` and `flatpak update` with one graphical password
prompt. Grew into a small dashboard around that: weather (+ alerts + AQI),
Pereprava backup status, today's Google Calendar events, and a to-do
sidebar synced with Google Tasks. Has a real system tray icon and can run
quietly in the background instead of always opening a window.

Zarya deliberately runs a loose sandbox — its whole purpose is managing the
*host* system (zypper, flatpak, systemctl), so it needs `flatpak-spawn --host`
for all of that. See the root `CLAUDE.md`'s note on Pereprava for the same
tradeoff and why sandboxing doesn't buy anything here.

## Running

```sh
pip install -e .
zarya
# or directly
python -m zarya.zarya
```

- Config: `~/.config/zarya/config.json` (or `~/.var/app/io.github.calstfrancis.zarya/config/zarya/config.json` under flatpak)
- Cache/state: `~/.cache/zarya/lastrun` (date of last successful update) and `lastresult.json` (last outcome, any result)
- Autostart entry: `~/.config/autostart/io.github.calstfrancis.zarya.desktop`, written/removed by the "Start at login" switch

## Version

Single source of truth: `version` in `pyproject.toml`, mirrored in `zarya/__init__.py`'s `__version__`. No separate release-name constant or `capture-screenshots.sh` yet (see the root CLAUDE.md's App capability matrix).

## Module map

| Path | Responsibility |
|---|---|
| `zarya/zarya.py` | Entry point — `ZaryaApplication`/`ZaryaWindow`, the update run state machine, section building (`_make_section`), config/marker/result I/O |
| `zarya/onboarding.py` | First-run wizard (`OnboardingWindow`) — city + optional Google Account connect, gated on `config["onboarded"]` |
| `zarya/preferences.py` | `PreferencesWindow` — Weather (location/units), Google (connect/disconnect, covers Calendar + Tasks), and a live-fetched calendar checklist (`config["calendar_ids"]`) |
| `zarya/weather.py` | Open-Meteo geocoding + hourly forecast + current/apparent temperature fetch, stdlib `urllib` only |
| `zarya/weather_table.py` | `WeatherTable` — hourly numbers grid (not a chart; see **Weather chart history** below) |
| `zarya/weather_alerts.py` | Environment Canada active alerts (ECCC MSC GeoMet OGC API, `weather-alerts` collection), bbox-around-point query |
| `zarya/weather_aqi.py` | Standard US EPA AQI (0-500) from Open-Meteo's air-quality API — deliberately *not* Canada's AQHI (1-10), which an earlier version used and which confused a real AQI reading (14) for AQHI's very different scale (1) |
| `zarya/backup_status.py` | Reads Pereprava's job JSON + `systemctl --user` status via one embedded Python script run through `flatpak-spawn --host python3 -c ...` |
| `zarya/system_health.py` | Disk space + CPU/GPU temperature (both `flatpak-spawn --host`, hwmon for temps, allowlisted to real CPU/GPU chip names) + drive SMART health (UDisks2) + battery health (UPower's `Capacity` property) — the latter two over the **system** D-Bus (`--system-talk-name`, not the usual session-bus `--talk-name`), read-only, no root/pkexec needed |
| `zarya/google_calendar.py` | OAuth2 + PKCE loopback flow (shared by Calendar and Tasks), `get_access_token()` (public, reused by `google_tasks.py`), `list_calendars()` + multi-calendar `fetch_today_events()` — stdlib only, no Google client libraries |
| `zarya/google_tasks.py` | Google Tasks API v1 CRUD (`@default` list) — list/add/set-done/delete, reuses `google_calendar.get_access_token()` |
| `zarya/todo_sidebar.py` | `TodoSidebar` — persistent right-side panel, backed entirely by Google Tasks (no local storage); shows a connect prompt when not connected |
| `zarya/keyring.py` | libsecret wrappers — Google refresh token storage (schema `io.github.calstfrancis.zarya.google_calendar`), covers both Calendar and Tasks scopes on one token |
| `zarya/tray.py` | `TrayIcon` — hand-rolled StatusNotifierItem D-Bus service (see **System tray** below) |
| `zarya/styles.py` | Fondwave CSS: the weather card's gradient, and the Konsole-scheme colors shared by the log view and the to-do sidebar |

## Why `flatpak-spawn --host` everywhere

Every privileged or host-state operation goes through it, never a bundled
helper binary:
- `pkexec sh -c "zypper ref && zypper dup -y && flatpak update --system -y"` — one prompt, one root shell. System flatpak updates are folded in here because they need the same polkit authority zypper does; running `flatpak update --system` unprivileged fails with "Deploy not allowed for user".
- `flatpak update --user -y` — unprivileged, separate step.
- `systemctl --user show/list-timers` and reading `~/.config/pereprava/jobs/*.json` — via an embedded script (`backup_status._STATUS_SCRIPT`) run once with `python3 -c`, rather than multiple round-trips.
- `pereprava` — launched directly (fire-and-forget `Gio.Subprocess`) by the Backups section's link-out button.

## Completion must be keyed on process exit, not stdout EOF

`run_step()` in `zarya.py` calls `proc.wait_async()` immediately after
spawning, in parallel with the line-reading loop — it does **not** wait for
the read loop to see EOF before calling the step's `done_callback`. This was
a real bug (dev1→dev2): `zypper`/`rpm` can fork a helper (gpg-agent, etc.)
that inherits the stdout pipe's write end and keeps it open well after the
actual command exits, so gating on EOF hangs forever between the zypper and
flatpak steps. `wait_async` watches the specific child PID and fires
regardless of what any grandchild does with the inherited fd.

## Google OAuth (Calendar + Tasks)

- Client type: Desktop app (installed-app), PKCE, loopback redirect
  (`http://127.0.0.1:<ephemeral-port>/callback`) — this only works because
  the manifest grants `--share=network` (joins the host network namespace),
  so the host's default browser can actually reach the sandbox's local
  server.
- `CLIENT_ID`/`CLIENT_SECRET` in `google_calendar.py` are committed in source
  deliberately — Google's own model doesn't treat a Desktop-app client secret
  as confidential (real security boundary is PKCE + the user's own Google
  login), and the repo is public.
- Consent screen is in **Production** status (not Testing) so refresh tokens
  don't expire after 7 days — Testing-mode tokens do, which would silently
  break the calendar/tasks sections weekly.
- Privacy policy / ToS required by the consent screen live on
  `calstfrancis.github.io` (`/privacy.html`, `/terms.html`), not in this repo
  — Zarya's own repo has no GitHub Pages site.
- **One connection, two scopes**: `google_calendar.SCOPE` is
  `calendar.readonly` + `tasks` (read/write — the to-do sidebar needs to
  create/complete/delete, not just read), requested together in a single
  consent. `google_tasks.py` reuses the same refresh token via
  `google_calendar.get_access_token()`. Widening the scope on an existing
  Google Cloud project requires the **Tasks API enabled** in that project
  (Cal's action, same as the Calendar API step) and the new scope added to
  the OAuth consent screen — and any already-connected user's stored
  refresh token predates the wider scope, so Tasks calls will fail for them
  until they disconnect and reconnect in Preferences.

## Fondwave styling

`styles.py` applies two CSS blocks at `Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION`:
- `.fondwave-card` (weather section only) — the dusk gradient, deliberately
  one branded card, not a theme-wide change. Everything else routes through
  libadwaita's named colors as usual. Note this rule's `label { color }` is
  loaded at APPLICATION priority, which beats libadwaita's own `.warning`/
  `.error` label colors (THEME priority) regardless of selector specificity —
  the weather-alert banner needed explicit `.fondwave-card label.warning`/
  `.error` overrides in the same stylesheet to get its colors back.
- `.fondwave-terminal` (update log **and** the to-do sidebar, per explicit
  feedback that the sidebar should match the terminal rather than use the
  dark gradient) — the Fondwave Konsole colorscheme's exact hexes,
  reproduced directly so it looks right whether or not that Konsole profile
  is installed. See `project_fondwave` in Cal's memory for the canonical
  palette this is drawn from.

## System tray

`tray.py` implements the StatusNotifierItem D-Bus interface directly (the
protocol underneath libappindicator) rather than depending on
`libayatana-appindicator`, which isn't in the `org.gnome.Platform` runtime
and would need its own flatpak module. Registers itself with whatever's
listening on `org.kde.StatusNotifierWatcher` (KDE ships one; GNOME needs an
extension) — confirmed this actually registers with a real watcher (queried
`RegisteredStatusNotifierItems`) before wiring it into the app at all. No
DBusMenu — just icon + click-to-toggle (`Activate`/`SecondaryActivate`/
`ContextMenu` all do the same thing). If no watcher is running, registration
just fails silently and the app behaves exactly as it did with no tray.

Needs `--talk-name=org.kde.StatusNotifierWatcher` in the manifest for the
sandboxed build to reach the watcher — the dev/test verification above ran
outside the sandbox and doesn't cover that grant by itself.

`--background` (a `GLib.OptionArg.NONE` main option, read via
`handle-local-options`) is what the autostart entry passes so the window
stays hidden on login; a plain `flatpak run` still opens it. Window
close (`close-request`) hides instead of quitting unless `self.tray.registered`
is false, in which case it falls through to a real close so the window can
never become unreachable. `app.hold()` keeps the `GApplication` alive while
hidden; "Quit Zarya" in the hamburger menu is the actual way out.

## Autorun reliability — login-triggered isn't enough

The autostart `.desktop` entry only runs once, at an actual login — it does
**not** re-fire on suspend/resume. On a machine that reboots/logs out only
occasionally but suspends daily in between (this one: weekly reboots, daily
suspend), that means the daily update would only ever run on reboot days
and silently never again in between, since the app then just sits resident
in the tray. Real bug found this way ("the autorun isn't firing", 2026-09-01).
Fixed with a 5-minute `GLib.timeout_add_seconds` poll (`_maybe_autorun` in
`ZaryaWindow.__init__`) that runs `start_updates()` whenever the day has
rolled over and autostart is enabled, independent of any fresh login.

Also: the autostart file's content (`AUTOSTART_CONTENT`) is only ever
written when the "Start at login" switch is toggled — a file from before a
template change (e.g. the `--background` flag added in v0.4.0) goes stale
and silently keeps launching with the old `Exec=` line forever. Fixed with
`_heal_stale_autostart_entry()`, called on every startup, which rewrites the
file if it's out of sync with the current template. Any future change to
`AUTOSTART_CONTENT` self-heals on the next launch instead of needing users
to re-toggle the switch.

## Weather chart history

The hourly weather display was originally a Cairo-drawn line/bar chart
(`weather_chart.py`, since deleted) with a hover crosshair. Replaced with the
current `weather_table.py` plain numbers grid on explicit feedback that a
line isn't actually usable for reading exact values at a glance — worth
remembering before reintroducing a chart here.
