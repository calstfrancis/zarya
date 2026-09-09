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
| `zarya/preferences.py` | `PreferencesWindow` — Weather (location/units), Google (connect/disconnect, covers Calendar + Tasks), a live-fetched calendar checklist (`config["calendar_ids"]`), and Updates (Enable/Disable the passwordless daily timer, via `system_updates.py`) |
| `zarya/system_updates.py` | Installs/removes the root systemd unit + timer for passwordless daily updates — see **Passwordless daily updates** below |
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
- `pkexec sh -c "zypper ref && zypper dup -y && flatpak update --system -y"` — one prompt, one root shell, for "Run Now"/manual updates. See **Passwordless daily updates** below for why the *automatic* daily case doesn't go through this at all anymore.
- `flatpak update --user -y` — unprivileged, separate step.
- `systemctl --user show/list-timers` and reading `~/.config/pereprava/jobs/*.json` — via an embedded script (`backup_status._STATUS_SCRIPT`) run once with `python3 -c`, rather than multiple round-trips.
- `flatpak run io.github.calstfrancis.pereprava` — launched fire-and-forget by the Backups section's link-out button. Not the bare `pereprava` command: that only exists on PATH for the install-script distribution (`~/.local/bin`), which `flatpak-spawn --host` doesn't reliably see — a real bug (0.11.1) where the button did nothing at all, no error, since the host command failed silently with no output captured to report it. `flatpak run <app-id>` doesn't depend on PATH.

## Passwordless daily updates (0.12.0)

`_maybe_autorun()`'s background poll used to call the same `pkexec`-prompted
`start_updates()` as the "Run Now" button, so the *automatic* daily update
popped a graphical password prompt too — genuinely unattended in name only.
Cal asked to fix that specifically, **not** to also make manual updates
passwordless (an earlier version of this feature did that via a polkit rule
scoped to one systemd unit, letting "Run Now" call `systemctl start`
without a password — reverted per feedback: that's more power than asked
for, since a polkit rule authorizes *any process running as Cal's user*,
not "Zarya specifically," and there was no need to remove the prompt from a
deliberate manual click in the first place).

What's actually here:
- **`zarya/data/zarya-system-update.service`** — a root-owned `Type=oneshot`
  systemd *system* unit running
  `zypper ref && zypper dup && (flatpak update --system -y || flatpak update --system -y)`
  (the `||` retry is the same flatpak-transient-failure retry that used to
  live in `zarya.py`'s Python, folded into the unit's shell command instead).
  `Restart=on-failure` + `RestartSec=30` + `StartLimitIntervalSec=600` /
  `StartLimitBurst=5` (**added 0.12.2**, live bug): found in the wild — a
  `Persistent=true` catch-up run (see the `.timer` bullet below) fired
  within seconds of waking from suspend and failed instantly with DNS
  resolution errors across every configured repo, because
  `network-online.target` being "reached" doesn't reliably mean DNS/real
  connectivity is actually working yet immediately post-resume. Up to 5
  retries, 30s apart, gives the network a real chance to come up without
  retrying forever if it's a genuine failure (a broken repo, a real
  conflict). `StandardOutput=`/`StandardError=append:/var/log/zarya-system-update.log`
  (also 0.12.2): a plain, world-readable file this service creates at its
  own default root umask — reading a root-owned unit's *journal* entries
  needs the `systemd-journal` group, which nothing here grants (deliberately
  — see the polkit-rule reasoning below), so a user diagnosing a real
  failure hit `journalctl`'s silent "-- No entries --" for exactly that
  reason before finding the real error via `sudo journalctl`. The log file
  sidesteps needing that group at all.
- **`zarya/data/zarya-system-update.timer`** — fires it daily at 04:00 with
  `Persistent=true`, the systemd-native version of the polling workaround
  described in **Autorun reliability** below: it catches up on the next
  boot/wake if the machine was suspended at 04:00, no app code needed. This
  is a fully independent trigger — root's own timer runs the update whether
  or not Zarya is even open, with **no polkit rule and no user-triggerable
  action involved at all** for this routine case.
- **`zarya/system_updates.py`** + **Preferences > Updates** — the one-time
  root setup, done *in the app*, not via a separate shell script someone has
  to find and know to run. Clicking "Enable" reads the two bundled unit
  files' bytes (they ship as package data, so they're inside the flatpak's
  own `/app`, which Python can read but the *host* can't see at all) and
  pipes them, over stdin, to a single `flatpak-spawn --host pkexec sh` —
  writing both files via quoted heredocs (`<<'ZARYA_UNIT_EOF'`, so content
  is never shell-interpreted), then `daemon-reload` + `enable --now`. One
  password prompt, no terminal, no file for anyone to go find. "Disable"
  reverses it (`systemctl disable --now` + `rm` the two files). Both are a
  single `pkexec` call each — see `system_updates.py`'s `enable()`/`disable()`.
  **The Enable button stays clickable even once already installed**
  (relabels to "Reinstall") — `enable()`'s script is idempotent
  (`systemctl enable --now` on an already-enabled timer is a safe no-op), so
  re-clicking is how an already-set-up machine picks up a bundled unit file
  fix (like the retry logic above) after an app update, without a
  Disable-then-Enable dance nothing would otherwise prompt for.

**`system_updates.get_status()`** is the single source of truth for reading
this unit's state — two sequential `systemctl show` calls (the timer, then
the service; **not** one call covering both unit names, since `systemctl
show unit1 unit2` repeats the same property names once per unit with no
per-unit prefix, so a naive flat-dict merge would silently let the second
unit's values clobber the first's for any shared property name), returning
whether it's installed, when it's next/was last triggered, the last run's
result, and `ran_today`/`succeeded_today`/`failed_today` convenience flags.
The latter two only go true once today's outcome is actually *settled* —
while `ActiveState` reads `"activating"` (either an attempt is currently
running, or it's between `Restart=on-failure` attempts — see the .service
bullet above), both stay false, since `Result`/`ExecMainExitTimestamp`
update on every individual attempt, not just the final one, and would
otherwise read a mid-retry failure as final. Used by Preferences' status
label (a real "last ran HH:MM, succeeded/failed", not just a static
"Enabled" — added 0.12.2 after a user reported "Zarya isn't showing it in
any way" when checking whether the timer had actually run) and by
`zarya.py`'s `_check_unit_already_ran_today()`, a thin wrapper
`start_updates()` uses for the dedup check below.

**`start_updates(interactive=...)`** in `zarya.py` is the one entry point
for both callers, and the flag is the entire behavioral difference:
- `interactive=True` (the Run Now button, `on_run_clicked`): always
  completes today's update. First checks whether the root timer already did
  the privileged part today — if so, skips straight to the unprivileged
  `flatpak update --user` step; if not, runs the **original, unmodified
  pkexec chain**, prompting exactly as it always has. A manual click is a
  deliberate, in-person action — a password prompt there is normal and was
  never the problem. **Exception**: if Zarya's own "already updated today"
  marker is already set (i.e. this is an explicit "Run Anyway" click, not
  the day's first), the dedup check is skipped entirely and a real re-run is
  always forced — a real regression, found and fixed same-day (0.12.1):
  "Run Anyway" could otherwise silently do less than asked, quietly
  reducing to just the flatpak step whenever the timer had already
  succeeded that day, defeating the whole point of an explicit forced
  re-run.
- `interactive=False` (`_maybe_autorun`'s poll): **never prompts.** If the
  timer already did the privileged part today, silently finishes with just
  the unprivileged flatpak step and marks the day done (notification, history,
  the works — same as any other completed run). If the timer hasn't run
  yet, it does nothing this poll and waits for the next one — Zarya no
  longer force-triggers a password prompt from the background under any
  circumstance. That's the actual fix; everything else here just supports it.
  **If the timer's own retries have genuinely exhausted and today's run is
  settled-failed** (`failed_today`, added 0.12.3 — found via a direct user
  question after the 0.12.2 incident: "is that going to appear as two
  failures pointlessly in the recent runs?"), it's recorded into
  history/notification exactly once via `finish(success=False)` — gated on
  `already_reported_timer_failure_today()` (a *separate* marker from
  `mark_done()`/`already_ran_today()`, since a failed automatic run should
  leave "Run Now" available, not flip it to "Run Anyway") so the same
  settled failure doesn't get re-recorded on every 5-minute poll for the
  rest of the day. Before this, a fully-exhausted automatic failure was
  silently invisible on the main dashboard — no dot, no notification, only
  visible by going to check Preferences > Updates directly.

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

Since 0.12.0 (see **Passwordless daily updates** above), once Preferences >
Updates > Enable has been clicked, `zarya-system-update.timer`'s own
`Persistent=true` independently solves the exact same suspend/resume
gap this section describes — for the *system* part specifically. This
5-minute poll is still what's actually responsible for the unprivileged
`flatpak update --user` half (which the root timer doesn't cover) and
remains the whole mechanism on a machine where `install.sh` hasn't been run
yet — kept as-is, not replaced.

## Window layout — scrollable content, pinned action bar

The main window's dashboard content (`root_box`, all the sections) lives
inside a `Gtk.ScrolledWindow` (vertical only), not directly in the toast
overlay — a fixed `set_default_size(980, 780)` doesn't fit on every real
screen (a real bug on a T490's display: the bottom button row rendered
below the visible screen with no way to reach it). The "Start at
login"/"Run Now"/"Cancel"/"Hide to Tray" row is added via
`Adw.ToolbarView.add_bottom_bar`, not appended into the scrollable
`root_box`, so it always stays visible regardless of window height or
screen size. Any future section added to the dashboard goes in `root_box`
(scrolls); anything that must always be reachable (like these controls)
goes on the toolbar view's top/bottom bars instead.

## Weather chart history

The hourly weather display was originally a Cairo-drawn line/bar chart
(`weather_chart.py`, since deleted) with a hover crosshair. Replaced with the
current `weather_table.py` plain numbers grid on explicit feedback that a
line isn't actually usable for reading exact values at a glance — worth
remembering before reintroducing a chart here.
