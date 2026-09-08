"""One-time in-app setup for the passwordless daily update (Preferences >
Updates). Deliberately not a separate shell script the user has to find and
run in a terminal — this is a single button click, one pkexec prompt, done
entirely inside the app. See "Passwordless daily updates" in CLAUDE.md.

The two systemd unit files are bundled as package data (zarya/data/) so
Python (running inside the sandbox, where /app is mounted) can read their
bytes directly and pipe them, over stdin, to a `pkexec sh` running on the
*host* — the host has no view into the sandbox's /app at all, so a bare
path reference wouldn't work; stdin crosses that boundary fine. A quoted
heredoc delimiter (<<'EOF') means the content is never shell-interpreted,
so this is safe regardless of what's in the files (not that it varies —
we wrote them ourselves, this isn't untrusted input).
"""

from pathlib import Path

from gi.repository import Gio, GLib

SYSTEM_UPDATE_SERVICE = "zarya-system-update.service"
SYSTEM_UPDATE_TIMER = "zarya-system-update.timer"

_DATA_DIR = Path(__file__).resolve().parent / "data"


def check_installed(callback):
    """Async: callback(bool) — whether the timer is currently installed."""
    launcher = Gio.SubprocessLauncher.new(
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
    )
    try:
        proc = launcher.spawnv(
            ["flatpak-spawn", "--host", "systemctl", "list-unit-files", SYSTEM_UPDATE_TIMER]
        )
    except GLib.Error:
        callback(False)
        return

    def on_done(source, result):
        try:
            _ok, stdout, _stderr = source.communicate_utf8_finish(result)
        except GLib.Error:
            callback(False)
            return
        callback(SYSTEM_UPDATE_TIMER in stdout)

    proc.communicate_utf8_async(None, None, on_done)


def _run_privileged_script(script, callback):
    """Async: callback(success, error_message_or_None). Runs `script` as
    root via `pkexec sh`, fed over stdin rather than as a command-line
    argument or a referenced file path (see module docstring)."""
    launcher = Gio.SubprocessLauncher.new(
        Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
    )
    try:
        proc = launcher.spawnv(["flatpak-spawn", "--host", "pkexec", "sh"])
    except GLib.Error as e:
        callback(False, str(e))
        return

    def on_done(source, result):
        try:
            _ok, stdout, _stderr = source.communicate_utf8_finish(result)
        except GLib.Error as e:
            callback(False, str(e))
            return
        if source.get_successful():
            callback(True, None)
        else:
            callback(False, stdout.strip() or f"exit status {source.get_exit_status()}")

    proc.communicate_utf8_async(script, None, on_done)


def enable(callback):
    """Async: callback(success, error_message_or_None). Installs both unit
    files and starts the timer — one pkexec prompt."""
    service_content = (_DATA_DIR / SYSTEM_UPDATE_SERVICE).read_text()
    timer_content = (_DATA_DIR / SYSTEM_UPDATE_TIMER).read_text()
    script = f"""set -e
cat > /etc/systemd/system/{SYSTEM_UPDATE_SERVICE} <<'ZARYA_UNIT_EOF'
{service_content}ZARYA_UNIT_EOF
cat > /etc/systemd/system/{SYSTEM_UPDATE_TIMER} <<'ZARYA_UNIT_EOF'
{timer_content}ZARYA_UNIT_EOF
systemctl daemon-reload
systemctl enable --now {SYSTEM_UPDATE_TIMER}
"""
    _run_privileged_script(script, callback)


def disable(callback):
    """Async: callback(success, error_message_or_None). Reverses enable()."""
    script = f"""systemctl disable --now {SYSTEM_UPDATE_TIMER} 2>/dev/null || true
rm -f /etc/systemd/system/{SYSTEM_UPDATE_SERVICE} /etc/systemd/system/{SYSTEM_UPDATE_TIMER}
systemctl daemon-reload
"""
    _run_privileged_script(script, callback)
