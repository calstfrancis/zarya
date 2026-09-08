#!/usr/bin/env bash
# capture-screenshots.sh — capture a fresh screenshot of Zarya
#
# Launches the app from source under a throwaway $HOME (so it never touches
# Cal's real config/data), inside an isolated Xvfb display forced via
# GDK_BACKEND=x11 (GTK4 otherwise prefers the real Wayland session and would
# render on the actual desktop). Waits for the window to render, screenshots
# just the window, and overwrites screenshots/zarya-main.png.
#
# Unlike Rubric/Gost/Kopilka/Zerkalo/Iskra/Skrizhal, Zarya has no local demo
# file to seed — Weather, System Health, Backups, and today's Events/Tasks
# are all read live from the network, the host system (via flatpak-spawn,
# unavailable outside the sandbox), or a connected Google account. So this
# capture only seeds a location and shows the app's genuine first-run state
# for everything else (each section's real empty/connect-prompt state) —
# not fabricated demo data, since there's no local file to fabricate it in.
# Weather is a live Open-Meteo fetch (no auth, no PII) for the seeded city.
#
# Requires: Xvfb, ImageMagick (magick), python3-gi/gtk4/libadwaita (same deps
# as running Zarya normally).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DEMO_HOME=$(mktemp -d /tmp/zarya-demo-home.XXXXXX)
OUT="screenshots/zarya-main.png"
OUT_DARK="screenshots/zarya-main-dark.png"
WINDOW_W=980
WINDOW_H=780

cleanup() {
  if [[ -n "${APP_PID:-}" ]]; then
    # dbus-run-session does NOT reliably forward SIGTERM to its own children
    # (the dbus-daemon it starts, and the target program it execs) — killing
    # only $APP_PID reliably leaves both running as orphans. Confirmed live
    # while debugging the hang this works around: after killing dbus-run-session
    # itself, its dbus-daemon and the still-running `python3 -m zarya.zarya`
    # were both left behind, PPID reparented to init, invisible to this
    # trap's original single `kill "$APP_PID"`.
    pkill -TERM -P "$APP_PID" 2>/dev/null || true
    kill "$APP_PID" 2>/dev/null || true
  fi
  [[ -n "${XVFB_PID:-}" ]] && kill "$XVFB_PID" 2>/dev/null || true
  rm -rf "$DEMO_HOME"
}
trap cleanup EXIT

echo "==> Seeding demo config in $DEMO_HOME"
mkdir -p "$DEMO_HOME/.config/zarya" "$DEMO_HOME/.cache/zarya"
cat > "$DEMO_HOME/.config/zarya/config.json" <<JSON
{
  "onboarded": true,
  "location": "Toronto, Canada",
  "units": "celsius",
  "health_expanded": false,
  "backups_expanded": false,
  "log_expanded": false
}
JSON
# System Health and Backups read live from the host's system D-Bus and
# Pereprava's own config — neither is namespaced by $HOME/XDG, so outside
# the flatpak sandbox they'd otherwise show Cal's real drive model, battery
# cycle count, and backup job names. Collapsed above so the capture never
# renders them. Also seed an "already updated today" marker so the capture
# doesn't show a real (and here, expected-to-fail-outside-the-sandbox)
# update attempt firing on first launch.
TODAY=$(date +%Y-%m-%d)
echo -n "$TODAY" > "$DEMO_HOME/.cache/zarya/lastrun"
cat > "$DEMO_HOME/.cache/zarya/lastresult.json" <<JSON
{"date": "$TODAY", "success": true, "time": "07:00"}
JSON
cat > "$DEMO_HOME/.cache/zarya/history.json" <<JSON
[{"date": "$TODAY", "success": true}]
JSON
# "Start at login" is on by default since v0.11.0 — seed the autostart
# entry directly so the capture reflects that (its state comes from
# whether this file exists, not a config key).
mkdir -p "$DEMO_HOME/.config/autostart"
cat > "$DEMO_HOME/.config/autostart/io.github.calstfrancis.zarya.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Zarya
Comment=Runs system and flatpak updates at login
Exec=flatpak run io.github.calstfrancis.zarya --background
Icon=io.github.calstfrancis.zarya
X-Flatpak=io.github.calstfrancis.zarya
NoDisplay=true
DESKTOP

# Isolated Xvfb display, well clear of any real display number in use.
DISPLAY_NUM=226
while [[ -e "/tmp/.X${DISPLAY_NUM}-lock" ]]; do
  DISPLAY_NUM=$((DISPLAY_NUM + 1))
done

echo "==> Starting isolated Xvfb on :$DISPLAY_NUM"
Xvfb ":$DISPLAY_NUM" -screen 0 1280x900x24 > "$DEMO_HOME/xvfb.log" 2>&1 &
XVFB_PID=$!
sleep 2

# A from-scratch dbus-run-session config, deliberately WITHOUT
# <standard_session_servicedirs/> — the default one (session.conf) includes
# it, which makes the "isolated" bus still discover the REAL system's
# /usr/share/dbus-1/services/*.service files and auto-activate real system
# services on request. Found live: Zarya's keyring lookup at window-
# construction time requests org.freedesktop.secrets, the isolated bus
# happily activates the REAL gnome-keyring-daemon (its .service file is
# still visible), and that daemon then hangs indefinitely waiting on
# PAM/unlock plumbing that never arrives in this headless context — Zarya's
# own GLib.Error handling for "service unreachable" never even triggers,
# since the request doesn't fail, it just never returns. Dropping the
# standard servicedirs directive means an unregistered name request fails
# immediately ("was not provided by any .service files") instead of
# triggering a real activation, which is what "isolated" should have meant
# in the first place.
cat > "$DEMO_HOME/dbus-session.conf" <<'DBUSCONF'
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <keep_umask/>
  <listen>unix:tmpdir=/tmp</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
DBUSCONF

# Capture the app once per colour scheme. libadwaita normally resolves
# light/dark from the desktop's settings portal, which on this machine always
# reports light. ADW_DISABLE_PORTAL=1 makes libadwaita read the GSettings
# color-scheme key instead, and GSETTINGS_BACKEND=keyfile feeds it a value we
# write into the throwaway config — forcing either scheme deterministically.
# XDG_CONFIG_HOME is redirected into the throwaway home *only for the child*
# so that keyfile never lands in Cal's real ~/.config; Zarya only calls
# GLib.get_user_config_dir() (like Zerkalo, not Path.home()), so it needs the
# full XDG override rather than just HOME.
#
# GDK_BACKEND=x11 + unsetting WAYLAND_DISPLAY is required: GTK4 prefers
# Wayland by default, which would otherwise connect to the real desktop
# session and render there instead of into the isolated Xvfb display.
#
# dbus-run-session isolates the session bus so a real running Zarya (dev
# build or flatpak) doesn't just relay-activate instead of actually
# launching this throwaway instance.
capture_scheme() {
  local scheme="$1" out="$2"
  mkdir -p "$DEMO_HOME/.config/glib-2.0/settings"
  cat > "$DEMO_HOME/.config/glib-2.0/settings/keyfile" <<KEYFILE
[org/gnome/desktop/interface]
color-scheme='$scheme'
KEYFILE

  echo "==> Launching Zarya ($scheme) inside the isolated display"
  # stdout/stderr go to a log file, not inherited from this script — a
  # background process that outlives this script (see cleanup()'s comment
  # on dbus-run-session not forwarding signals to its children) would
  # otherwise keep holding this script's own stdout pipe open, hanging
  # anything reading from it (e.g. a `| tail` on the caller's side) even
  # after this script itself has been killed by an outer `timeout`. This is
  # what actually turned one hung capture into an hours-long stuck terminal
  # command, on top of the dbus activation hang above.
  env -u WAYLAND_DISPLAY GDK_BACKEND=x11 \
    HOME="$DEMO_HOME" XDG_CONFIG_HOME="$DEMO_HOME/.config" XDG_DATA_HOME="$DEMO_HOME/.local/share" \
    XDG_CACHE_HOME="$DEMO_HOME/.cache" XDG_STATE_HOME="$DEMO_HOME/.local/state" \
    ADW_DISABLE_PORTAL=1 GSETTINGS_BACKEND=keyfile DISPLAY=":$DISPLAY_NUM" \
    dbus-run-session --config-file="$DEMO_HOME/dbus-session.conf" -- python3 -m zarya.zarya \
    > "$DEMO_HOME/zarya-$scheme.log" 2>&1 &
  APP_PID=$!

  echo "==> Waiting for window to render (incl. the live weather fetch)"
  sleep 10

  echo "==> Capturing and cropping to the app window -> $out"
  DISPLAY=":$DISPLAY_NUM" magick x:root -crop "${WINDOW_W}x${WINDOW_H}+0+0" +repage "$out"

  # See cleanup()'s comment: dbus-run-session doesn't reliably forward this
  # to its own children, so kill them explicitly too, not just $APP_PID.
  pkill -TERM -P "$APP_PID" 2>/dev/null || true
  kill "$APP_PID" 2>/dev/null || true
  wait "$APP_PID" 2>/dev/null || true
  APP_PID=
}

capture_scheme default     "$OUT"
capture_scheme prefer-dark "$OUT_DARK"

echo "Done. Wrote $OUT and $OUT_DARK"

# Publish web-ready copies into the personal website repo, one PNG + WebP per
# scheme, named as the site expects (<slug>.png/.webp + <slug>-dark.png/.webp).
# The capture crop already matches the site's image dimensions, so this is a
# straight convert+copy — no resize. Override the destination with
# WEBSITE_DIR=/path ./capture-screenshots.sh; if it doesn't exist the export is
# skipped with a note rather than failing. The website is a separate repo —
# commit and push it there yourself after reviewing the refreshed images.
SLUG="zarya"
WEBSITE_DIR="${WEBSITE_DIR:-$(dirname "$SCRIPT_DIR")/calstfrancis.github.io}"
if [[ -d "$WEBSITE_DIR" ]]; then
  echo "==> Publishing web images to $WEBSITE_DIR"
  cp "$OUT"      "$WEBSITE_DIR/$SLUG.png"
  cp "$OUT_DARK" "$WEBSITE_DIR/$SLUG-dark.png"
  magick "$OUT"      -quality 80 "$WEBSITE_DIR/$SLUG.webp"
  magick "$OUT_DARK" -quality 80 "$WEBSITE_DIR/$SLUG-dark.webp"
  echo "    wrote $SLUG.{png,webp} and $SLUG-dark.{png,webp}"
else
  echo "NOTE: website dir not found ($WEBSITE_DIR) — skipping web export."
fi
