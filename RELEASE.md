# Zarya v0.12.2 "True North"

**Released:** 2026-09-09

## What's new

Found and fixed the same day, from a real report of the daily update
appearing not to have run:

- **The daily update timer could fail instantly right after waking from
  suspend**, with DNS resolution errors across every configured repo.
  `network-online.target` being "reached" doesn't reliably mean DNS/real
  connectivity is actually working yet that soon after resume, and the
  timer's suspend-catch-up behavior (`Persistent=true`) has no reason to
  wait for that on its own. The service now retries up to 5 times, 30
  seconds apart, before giving up — enough for the network to actually
  come back without retrying forever on a real, non-transient failure.
- **A failed run's real error was invisible without `sudo`.** Reading a
  root-owned systemd unit's journal entries needs the `systemd-journal`
  group, which this feature deliberately doesn't grant (same reasoning as
  not installing a broader polkit rule than it needs) — so a plain
  `journalctl -u zarya-system-update.service` silently showed "-- No
  entries --" with no hint why. The service now also writes its own
  output to a plain, world-readable log file
  (`/var/log/zarya-system-update.log`), and Preferences > Updates' failure
  message points there instead.
- **"Enable" in Preferences > Updates became permanently disabled** once
  already set up, with no way to push a fixed unit file (like the retry
  logic above) to an already-enabled machine short of manually clicking
  Disable first. It now stays clickable (relabeled "Reinstall") and
  re-syncs the installed unit files with whatever the app currently
  bundles — if you're upgrading from 0.12.0 or 0.12.1 and already clicked
  Enable, click it again to pick up this fix.

See [CHANGELOG.md](CHANGELOG.md) for everything since earlier releases,
including v0.12.1 "Steady Hours" (weather table now shows ±12 hours around
now) and v0.12.0 "Silent Dawn" (passwordless daily updates, set up in
Preferences).

## Download

| Method | Platform |
|---|---|
| Flatpak (`calstfrancis` repo) | Any Linux with Flatpak installed |

## Installation

```bash
flatpak remote-add --user calstfrancis \
  https://calstfrancis.github.io/flatpak/calstfrancis.flatpakrepo
flatpak install calstfrancis io.github.calstfrancis.zarya
```

Already installed? `flatpak update` picks this up — and if you'd already
enabled passwordless daily updates before this release, click "Reinstall"
in Preferences > Updates afterward to push the retry fix to your system.

## Running

```bash
flatpak run io.github.calstfrancis.zarya
```

---

## Full changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete history.
