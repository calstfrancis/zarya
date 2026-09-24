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
| `zarya/preferences.py` | `PreferencesWindow` — Weather (location/units), Google (connect/disconnect, covers Calendar + Tasks), a live-fetched calendar checklist (`config["calendar_ids"]`), and Updates (a "Start at login" `Adw.SwitchRow` since 0.16.0, plus Enable/Disable the passwordless daily timer, via `system_updates.py`) |
| `zarya/system_updates.py` | Installs/removes the root systemd unit + timer for passwordless daily updates — see **Passwordless daily updates** below |
| `zarya/weather.py` | Open-Meteo geocoding + hourly forecast + current/apparent temperature fetch, stdlib `urllib` only |
| `zarya/weather_table.py` | `WeatherTable` — hourly numbers grid (not a chart; see **Weather chart history** below) |
| `zarya/weather_alerts.py` | Environment Canada active alerts (ECCC MSC GeoMet OGC API, `weather-alerts` collection), bbox-around-point query |
| `zarya/weather_aqi.py` | Standard US EPA AQI (0-500) from Open-Meteo's air-quality API — deliberately *not* Canada's AQHI (1-10), which an earlier version used and which confused a real AQI reading (14) for AQHI's very different scale (1) |
| `zarya/backup_status.py` | Reads Pereprava's job JSON + `systemctl --user` status via one embedded Python script run through `flatpak-spawn --host python3 -c ...` |
| `zarya/system_health.py` | Disk space + CPU/GPU temperature (both `flatpak-spawn --host`, hwmon for temps, allowlisted to real CPU/GPU chip names) + drive SMART health (UDisks2) + battery health (UPower's `Capacity` property) — the latter two over the **system** D-Bus (`--system-talk-name`, not the usual session-bus `--talk-name`), read-only, no root/pkexec needed |
| `zarya/disk_growth.py` | Sizes of top-level (non-hidden) directories directly under the host's real home, via `flatpak-spawn --host sh -c 'du -sb ...'` — snapshotted at most once/day into `~/.cache/zarya/disk_growth_history.json` (pruned past 40 days), compared against the closest snapshot ≥7 days old to report the top 5 growing directories |
| `zarya/habits.py` | A small local daily habit tracker — add/remove habits, mark done for today, current streak — no external API. Durable data (not disposable cache), so it lives at `~/.local/share/zarya/habits.json` via `GLib.get_user_data_dir()`, unlike the cache-dir state above |
| `zarya/google_calendar.py` | OAuth2 + PKCE loopback flow (shared by Calendar and Tasks), `get_access_token()` (public, reused by `google_tasks.py`), `list_calendars()` + multi-calendar `fetch_today_events()` — stdlib only, no Google client libraries |
| `zarya/google_tasks.py` | Google Tasks API v1 CRUD (`@default` list) — list/add/set-done/delete, reuses `google_calendar.get_access_token()` |
| `zarya/todo_sidebar.py` | `TodoSidebar` — persistent right-side panel, backed entirely by Google Tasks (no local storage); shows a connect prompt when not connected. Completed tasks collapse under a "Completed (N)" toggle; sits above the Habits card in the sidebar (`zarya.py` builds that outer `sidebar_box`, since 0.16.0) |
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

## Window layout — scrollable content (0.16.0: no more pinned action bar)

The main window's dashboard content (`root_box`: Weather, Today's Events,
the status row) lives inside a `Gtk.ScrolledWindow` (vertical only), not
directly in the toast overlay — a fixed window size doesn't fit on every
real screen (a real bug on a T490's display, back when there was a bottom
button row: it rendered below the visible screen with no way to reach it).
Since 0.16.0 there's no bottom bar at all — see **Main window redesign**
below for why and where its contents moved. Any future section added to the
main column goes in `root_box` (scrolls); anything that must always be
reachable belongs on the toolbar view's top bar (the header) instead, same
as `self.restart_banner`.

## Main window redesign (0.16.0)

A UI/UX pass triggered by Cal sharing two real screenshots (unmaximized —
"how it'll usually be used" — and maximized) and asking for better use of
space, ordering, and friendliness. Mockups were built first as a canvas
Artifact, reviewed, then implemented directly in GTK (not a pixel port of
the HTML mockup — GTK/libadwaita has its own idioms). Kept: `root_box`
scrolling, the sidebar `Gtk.Paned`, the Fondwave weather-card styling,
every existing fetch/render function's actual logic. Changed:

- **System Health, Backups, and Disk Growth folded into three compact
  status cards** (System, Backups, Updates) in one row (`status_row`),
  replacing what used to be three-to-four always-expanded `Gtk.Expander`
  sections plus the bottom button row. Each card is a `Gtk.MenuButton`
  (`_make_status_card`) whose face shows a title + one-line value + an
  optional detail line, and whose popover holds the existing detail
  content boxes (`self.health_box`, `self.backup_box`, etc. — unchanged
  widgets, just re-parented into a popover instead of an expander). A card
  only gets the `.warning`/`.error` CSS class (`_set_card_state`) when
  there's actually something to flag — Disk Growth moved into the System
  popover specifically (both are "state of the machine"), rather than
  getting a fourth card of its own. This is where most of the vertical
  space savings comes from: the common "everything's fine" case is one
  quiet row instead of a full page of "OK" lines.
- **The bottom button row is gone.** "Start at login" moved to Preferences
  > Updates as an `Adw.SwitchRow` (`PreferencesWindow.autostart_row`,
  wired via an `on_autostart_toggled(enabled: bool)` callback into
  `ZaryaWindow.on_autostart_toggled` — the callback signature changed from
  a `Gtk.Switch` "state-set" handler `(switch, state) -> bool` to a plain
  `(enabled) -> None`, since there's no switch object here to return
  through anymore). Run Now/Cancel, the run-history dots, and the Update
  Log all moved into the Updates card's popover — same widgets
  (`self.run_button`, `self.history_box`, `self.text_view`, …), just
  re-parented. `ZaryaApplication.on_onboarding_finished` no longer touches
  a `self.window.autostart_switch` (deleted) — it just writes the
  autostart file directly, same as before the switch existed.
- **Habits moved into the sidebar**, appended below `TodoSidebar` in a new
  `sidebar_box` that's the paned's actual end child (previously
  `TodoSidebar` was the end child directly) — both To-Do and Habits are
  "things I check off today," so they read better together than Habits
  being a separate section at the bottom of the scrolling main column.
  `self.habits_box` itself (and `render_habits()`) didn't change at all,
  only its container.
- **The header now carries a date/status title** (`self.window_title`, an
  `Adw.WindowTitle`) and a single "refresh everything" button
  (`on_refresh_all_clicked`), replacing each section's own per-section
  refresh button (weather/events/health/backups/disk-growth all had one).
  `_update_window_title()` recomputes "Thursday, September 24" / "Good
  afternoon · Toronto · all clear" (or "N things need attention", counted
  from which status cards currently carry `.warning`/`.error`) — called
  after every render that could change a card's state, plus once every
  600s off the existing gradient-refresh timer.
- **The restart-after-update prompt became a banner, not a dialog** — see
  **Restart-after-update prompt** below, updated for this release.
- Smaller UX fixes bundled into the same pass: the weather table's Rain
  row hides entirely on a no-rain day (`WeatherTable.set_data` computes
  `has_rain` from the precip array); Today's Events gained a "now" divider
  line (`_make_now_line`) between past and upcoming events, dimmed past
  events (`opacity(0.55)` on the row), and a per-calendar color dot
  (`cal-dot-0..5` CSS classes, index = `hash(calendar_id) % 6` — not
  Google's real calendar colors, just enough for same-calendar events to
  visually match each other); completed to-dos collapse under a
  "Completed (N)" toggle in `TodoSidebar` instead of staying inline
  forever; every delete/remove button (to-dos, habits) now only shows on
  hover, via `_wire_hover_reveal` — a small helper using
  `Gtk.EventControllerMotion` to set opacity directly, not CSS `:hover`,
  since that pseudo-class doesn't reliably bubble from a plain GTK4
  container to its children the way it does in web CSS.
- **Fixed a real, independently-found bug while in this code anyway**:
  `WeatherTable.center_on_now()`'s poll for the grid's width to become
  nonzero gave up after ~600ms (20 attempts × 30ms), which wasn't always
  enough on first launch — the hourly strip would silently stay scrolled
  to its leftmost (oldest) hours instead of centering on "now". Bumped to
  ~3s (100 attempts); the poll still stops immediately once the width
  resolves, so this costs nothing in the normal case.

**Maximized-width reflow added immediately after, same 0.16.0 release**,
once asked for specifically: `self.wide_row` (a plain `Gtk.Box`, unparented
at construction) plus one `Adw.Breakpoint` on the window itself
(`Adw.BreakpointCondition.new_length(MIN_WIDTH, 1200px)`), connected to
`_on_wide_layout`/`_on_narrow_layout`. Rather than building two separate
copies of Today's Events and the status row for narrow vs. wide, the
breakpoint's `apply`/`unapply` handlers **re-parent the same widgets**:
`self.root_box.remove(...)` them out of the single scrolling column,
`self.status_row.set_orientation(VERTICAL)` (so the three cards stack in a
narrower column instead of sitting in a row), append both into
`self.wide_row`, then `self.root_box.insert_child_after(self.wide_row,
self.weather_expander)`. `unapply` does the exact reverse, restoring
`HORIZONTAL`/`homogeneous=True` on `status_row` and putting
`events_expander`/`status_row` back into `root_box` directly.
`Gtk.Box.insert_child_after` is what makes this work without needing to
track/restore explicit child indices. Each status card needs
`set_hexpand(True)` (added in `_make_status_card`) so it actually fills the
narrower wide-mode column instead of shrinking to its label's natural
width — harmless in the narrow/homogeneous row too, since `homogeneous`
already forces equal widths there regardless of `hexpand`.

**Testing this needed a real window manager**, not just Xvfb — under bare
Xvfb (no WM), `Gtk.Window.maximize()` is a no-op (nothing handles the
maximize hint), so a naive headless test showed no reflow at all and looked
like a bug that wasn't one. Confirmed by adding `fluxbox` (available on
this machine) between starting Xvfb and launching the app in the manual
test session — maximizing then genuinely resizes the window and the
breakpoint fires. Not wired into `capture-screenshots.sh` (that script
deliberately captures only the normal unmaximized window, per its own
comments), so this reflow has no automated screenshot coverage yet; verify
by hand (or with a similar fluxbox-backed manual run) if touching this code
again. Also verified maximize → unmaximize → maximize → unmaximize in one
session doesn't leak or duplicate widgets — `wide_row` ends each cycle
empty and unparented, ready to be reused next time.

**Two real bugs found from an actual screenshot Cal took after updating,
not caught by the fluxbox testing above (0.17.1):**

- **`.status-card` had no visible background/border at all in the neutral
  ("ok") state** — only `.warning`/`.error` set a background/border, so a
  healthy card was just bare text floating with padding, not a card. Fixed
  by giving `.status-card` a real base look (`@card_bg_color`/
  `@card_fg_color`/`@borders`, same named-color approach as everywhere
  else), with the warning/error rules now only overriding the color on top
  of that base rather than being the only state that painted anything.
- **`status_row` itself was stretching to fill most of the wide layout's
  width**, instead of staying a narrow column next to Events. Cause:
  `_make_status_card` sets `card.set_hexpand(True)` on each card (needed so
  a card fills `status_row`'s width once stacked vertically in wide mode)
  — but `Gtk.Box` propagates a child's `hexpand` up to the box itself when
  the box hasn't set its own value, so `status_row` inherited hexpand=True
  from its card children and then claimed all the leftover space in
  `wide_row` instead of respecting its `set_size_request(280, -1)`. Fixed
  with an explicit `self.status_row.set_hexpand(False)` in
  `_on_wide_layout` (and `set_hexpand(True)` restored in
  `_on_narrow_layout`, where filling the full column width under Events
  *is* wanted). Worth remembering generally: setting `hexpand` on a
  container's children can silently change the container's own effective
  expand behavior unless the container's `hexpand` is pinned explicitly.

**Wide layout shows each card's full detail inline, not behind a click
(0.17.2)** — Cal's next screenshot showed the 0.17.0/0.17.1 wide layout was
still just the same one-line compact cards (System/Backups/Updates) stacked
in a column, matching the mockup's *position* but not what the mockup
actually showed on each card face: full inline detail (storage bars, the
backup job list, the update log/history/buttons), no click needed. Fixed by
giving each status card a **second, wide-only representation**
(`_make_wide_card`: a plain `.status-card` box with just an icon+title
header, no popover) and moving the *same* detail-body widget
(`self.system_detail_body`/`backups_detail_body`/`updates_detail_body` —
what used to be built directly as each popover's child) between the
popover and the wide card's body at breakpoint time:
`_on_wide_layout`/`_on_narrow_layout` now loop over
`_STATUS_CARD_NAMES = ("system", "backups", "updates")` and, per name,
`compact_card.get_popover().set_child(None)` +
`wide_card.append(detail_body)` (or the exact reverse) — never two copies
of the same content, same pattern as moving `events_expander`/the status
column between `root_box` and `wide_row`. `self.wide_status_column`
(replacing the old approach of just reusing `status_row` reoriented
vertically) is a plain `Gtk.Box` holding the three wide cards, sized/
hexpand-pinned the same way `status_row` was. Card color state
(`.warning`/`.error`) now needs to reach *both* representations, so
`_set_card_state(card, kind)` callers were replaced with
`_set_status_severity(name, kind)`, which applies it to
`{name}_card` and `{name}_wide_card` together — remember to call the
severity setter, not `_set_card_state` directly, from any new code path
that changes a card's state, or the wide-mode card will silently fall out
of sync with the compact one.

## Weather chart history

The hourly weather display was originally a Cairo-drawn line/bar chart
(`weather_chart.py`, since deleted) with a hover crosshair. Replaced with the
current `weather_table.py` plain numbers grid on explicit feedback that a
line isn't actually usable for reading exact values at a glance — worth
remembering before reintroducing a chart here.

## Dashboard auto-refresh (0.13.0)

Today's Events, System Health, and Backups used to only update on manual
refresh or app launch — added independent `GLib.timeout_add_seconds` polls
in `ZaryaWindow.__init__`, same pattern as weather's existing hourly timer:
events every 900s, health every 300s, backups every 600s (cheaper local
reads get shorter intervals; the Google Calendar API call gets the longest).
Disk Growth also has one at 21600s (6h), mostly to catch a snapshot on a
machine left open across midnight — see below for why more frequent doesn't
help it. Each timer callback just calls the section's existing `fetch_*()`
and returns `True` to keep repeating.

## Weather gradient tracks the solar day (0.13.0, fixed 0.15.0)

`.fondwave-card`'s gradient used to be a fixed set of 5 colors. It's now
computed from a 6-color dark→light ramp (`styles._GRADIENT_RAMP`): a
"daylight factor" in [0, 1] slides a 5-color window across the ramp, so the
whole gradient shifts one step lighter as the factor rises.

**0.13.0's first version of this was wrong**: `daylight_factor()` used a
single `0.5 - 0.5*cos(...)` over the full 24h, phased to peak at solar noon
— but a full-period cosine is always symmetric, so it always modeled
exactly 12 hours of "daylight" and 12 of "night" regardless of the actual
day length. On a short winter day (sunrise 08:00, sunset 16:30 — 8.5 hours
of real daylight) it would still show a bright gradient until ~18:00, two
hours after actual sunset. **Fixed in 0.15.0**: `daylight_factor(now,
sunrise_hour, sunset_hour)` is now a half-sine arc *between* sunrise and
sunset specifically (`sin(pi * (hour - sunrise) / (sunset - sunrise))`) —
0 at sunrise, 1 at the midpoint (solar noon, by construction), back to 0 at
sunset — and flat 0.0 outside that window, since 0 is already the ramp's
darkest end and doesn't need its own night-time curve. `weather.sun_hours()`
returns today's real sunrise/sunset as fractional hours once weather has
loaded (`styles.set_sun_hours`, called from `render_weather`); before that,
or if sunrise/sunset didn't come back, it falls back to the old fixed-noon
cosine as a reasonable default. Recomputed every 600s by
`_on_gradient_refresh_timer` via `styles.refresh_weather_gradient()`, which
updates a dedicated `Gtk.CssProvider` in place (`styles._gradient_provider`)
rather than re-adding one each time, so it never stacks providers on the
display. Sunrise/sunset themselves come from Open-Meteo's `daily` block
(`sunrise,sunset` added to the existing params) — no new API or network call.

## Precipitation gradient tint (0.15.0)

A second, semi-transparent `linear-gradient` layer is prepended before the
daylight gradient in `.fondwave-card`'s `background-image` (CSS supports
multiple comma-separated background layers; the first listed renders on
top) — `styles._precip_overlay_css()`, driven by `weather.precip_tint()`
mapping the *current* Open-Meteo weather code (added `weather_code,
precipitation` to the `current` params, not just the daily/hourly ones
already fetched) to a (kind, alpha) pair: blue-gray for rain, pale
near-white for snow, with alpha hand-tuned per code so heavier variants
(e.g. 65 "heavy rain" vs 61 "light rain") tint more strongly. `None` when
the current code isn't an active-precipitation one, which clears the
overlay entirely (plain daylight gradient, same as always). Set via
`styles.set_precip_tint()` alongside `set_sun_hours()` in `render_weather`.

## Day-length delta (0.15.0)

`weather.day_length_delta_minutes()` compares today's sunrise/sunset
against yesterday's — both already present in the same `fetch_today()`
response thanks to `past_days=1` (yesterday sits at daily-array index 0,
one before `TODAY_INDEX`), so this needed no extra request, just reading
data already being fetched and discarded. Shown in the weather card's
second row as "+Nm daylight" / "−Nm daylight", omitted entirely on a
day-over-day tie (`round(delta) == 0`).

## Disk Growth section (0.13.0)

Reports which top-level home directories grew the most in the last week.
Sizes come from `du -sb "$HOME"/*/` via `flatpak-spawn --host sh -c ...` —
a real host shell command, not a Python `os.walk`, since `du` walking a
large tree is much cheaper done by the host's own C binary than round-
tripped through Python. Snapshots are taken at most once per calendar day
(`disk_growth.record_snapshot` overwrites today's entry if one already
exists) into `~/.cache/zarya/disk_growth_history.json`, so the section
naturally builds a week of history over a week of normal daily use without
needing a dedicated snapshot timer — the periodic refresh above is just a
display refresh plus a safety net for a machine left open past midnight.
Growth is computed against the closest snapshot that's ≥7 days old (not
"exactly 7 days old", since the app won't always be open at the same time
every day). Shows "collecting a week of history" until one exists.

## Habits section (0.13.0, moved into the sidebar in 0.16.0)

A minimal local daily habit tracker — no external account, no API. Lived as
its own always-expanded section at the bottom of the scrolling main column
through 0.13.0–0.15.0; moved into the sidebar below To-Do in 0.16.0 (see
**Main window redesign**) — same box, same `render_habits()`, just
re-parented. Habits
are added/removed via a `+` button in the section header (`Adw.AlertDialog`
+ `Adw.EntryRow`, the modern libadwaita dialog pattern rather than a
one-off `Adw.Window`). Each row is a flat, name-as-label toggle button
following the house **Status bar with name-as-label toggles** convention
(root CLAUDE.md) — reuses the Fond suite's existing `.fond-statusbar` /
`.fond-toggle-active` CSS classes from `style/fond.css` (weight-only active
state, not a filled chip) rather than inventing new CSS for this one
section. Streak (`habits.current_streak`) counts consecutively backward
from today if today's marked done, or from yesterday otherwise — so the
streak doesn't drop to zero the instant a new day starts, only once a full
day is actually missed. Each row also shows `habits.week_count` — a rolling
7-day window (today back to 6 days ago), not calendar-week-aligned, added
0.14.0.

## Moon phase (0.14.0)

`weather.moon_phase()` is a plain astronomical calculation (days since a
known new moon, mod the synodic month's average length) — no extra network
call, no new API. Shown next to sunrise/sunset in the weather card. Accurate
to well under a day, which is all a dashboard reading needs; don't reach
for a real ephemeris library here.

## Restart-after-update prompt (0.14.0, changed to a banner in 0.16.0)

`ZaryaWindow.finish()` (the update run's completion handler) calls
`maybe_offer_restart(full_text)` on success, which does a plain substring
check for `APP_ID` in the full update log — the same best-effort spirit as
`summarize_updates()` right above it, not a real before/after version diff.
Matters because a `flatpak update` only replaces files on disk; the
already-running Zarya process keeps executing its old code in memory until
actually relaunched, whether the update ran interactively (Run Now) or
silently in the background (the daily autorun poll) — so this can pop the
window back up (`self.present()`) even if it was hidden in the tray.
**0.14.0 showed this as an `Adw.AlertDialog`; 0.16.0 changed it to
`self.restart_banner` (`Adw.Banner`, revealed via `set_revealed(True)`)** —
part of the same pass that removed the modal dialog pattern from the main
window in favor of quieter, non-blocking UI, and specifically less
disruptive than a modal if this fires from the silent background autorun
while Cal is mid-task elsewhere; it stays up (not auto-dismissed) until
"Restart Now" is clicked or the window is next closed. "Restart Now" itself
is unchanged: launches a fresh `flatpak run io.github.calstfrancis.zarya`
via `flatpak-spawn --host` (same pattern as the "Open Pereprava" button)
before quitting this instance — spawn-then-quit, not quit-then-spawn, so
there's no gap with no Zarya running if the spawn itself fails.
