# Changelog

## [0.1.0-dev1] — dev

- Initial version: runs `zypper ref && zypper dup` (single pkexec prompt) and
  `flatpak update`, with live output in a GTK4/libadwaita window.
- Skips re-running if already updated today; "Run Anyway" button to force it.
- Optional "Start at login" toggle that writes a plain XDG autostart entry.
