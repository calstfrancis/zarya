# Changelog

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
