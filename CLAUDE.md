# Zarya — Developer Notes

## What it is

A GTK4/libadwaita morning dashboard, flatpak-packaged. Core job: run
`zypper ref && zypper dup` and `flatpak update` with one graphical password
prompt. Grew into a small dashboard around that: weather, Pereprava backup
status, and today's Google Calendar events.

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
| `zarya/onboarding.py` | First-run wizard (`OnboardingWindow`) — city + optional Google Calendar connect, gated on `config["onboarded"]` |
| `zarya/preferences.py` | `PreferencesWindow` — Weather (location/units) and Calendar (Google connect/disconnect) pages |
| `zarya/weather.py` | Open-Meteo geocoding + hourly forecast fetch, stdlib `urllib` only |
| `zarya/weather_table.py` | `WeatherTable` — hourly numbers grid (not a chart; see **Weather chart history** below) |
| `zarya/backup_status.py` | Reads Pereprava's job JSON + `systemctl --user` status via one embedded Python script run through `flatpak-spawn --host python3 -c ...` |
| `zarya/google_calendar.py` | OAuth2 + PKCE loopback flow, token refresh, Calendar API v3 fetch — stdlib only, no Google client libraries |
| `zarya/keyring.py` | libsecret wrappers — Google refresh token storage (schema `io.github.calstfrancis.zarya.google_calendar`) |
| `zarya/styles.py` | Fondwave CSS: the weather card's gradient, and the log view's Konsole-scheme colors |

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

## Google Calendar OAuth

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
  break the calendar section weekly.
- Privacy policy / ToS required by the consent screen live on
  `calstfrancis.github.io` (`/privacy.html`, `/terms.html`), not in this repo
  — Zarya's own repo has no GitHub Pages site.
- Scope: `calendar.readonly` only.

## Fondwave styling

`styles.py` applies two CSS blocks at `Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION`:
- `.fondwave-card` (weather section only) — the dusk gradient, deliberately
  one branded card, not a theme-wide change. Everything else routes through
  libadwaita's named colors as usual.
- `.fondwave-terminal` (update log) — the Fondwave Konsole colorscheme's exact
  hexes, reproduced directly so it looks right whether or not that Konsole
  profile is installed. See `project_fondwave` in Cal's memory for the
  canonical palette this is drawn from.

## Weather chart history

The hourly weather display was originally a Cairo-drawn line/bar chart
(`weather_chart.py`, since deleted) with a hover crosshair. Replaced with the
current `weather_table.py` plain numbers grid on explicit feedback that a
line isn't actually usable for reading exact values at a glance — worth
remembering before reintroducing a chart here.
