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

import datetime
import re
from pathlib import Path

from gi.repository import Gio, GLib

SYSTEM_UPDATE_SERVICE = "zarya-system-update.service"
SYSTEM_UPDATE_TIMER = "zarya-system-update.timer"

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def get_status(callback):
    """Async: callback(dict) — a full status snapshot, so Preferences >
    Updates (and anywhere else that cares) can show something more useful
    than a static "Enabled" — and so a "did it actually run" question can
    be answered by looking, not guessing. Keys:
      next_trigger: str|None — when the timer is next scheduled to fire
                    (systemd's own formatted timestamp text), or None if
                    the timer was never installed/enabled
      last_trigger: str|None — when the timer last actually fired (this is
                    the timer *firing*, not the service *succeeding* — a
                    fired-but-failed run still updates this)
      last_result: str|None — the service's Result from its last run
                    ("success", "exit-code", ...), or None if it's never
                    run at all
      ran_today / succeeded_today: bool — convenience flags derived from
                    the service's own exit timestamp, used by zarya.py to
                    avoid redundantly re-prompting for something the timer
                    already handled today
    """
    launcher = Gio.SubprocessLauncher.new(
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
    )
    try:
        # Two separate `systemctl show` calls, not one covering both units —
        # `systemctl show unit1 unit2` repeats the SAME property names once
        # per unit with no reliable per-unit prefix, so merging into one
        # flat dict would silently let the second unit's values clobber the
        # first's for any property name both happen to share.
        proc = launcher.spawnv([
            "flatpak-spawn", "--host", "systemctl", "show", SYSTEM_UPDATE_TIMER,
            "--property=NextElapseUSecRealtime,LastTriggerUSec,UnitFileState",
        ])
    except GLib.Error:
        callback(_empty_status())
        return

    def on_timer_done(source, result):
        try:
            _ok, stdout, _stderr = source.communicate_utf8_finish(result)
        except GLib.Error:
            callback(_empty_status())
            return
        timer_props = _parse_show(stdout)
        if timer_props.get("UnitFileState") not in ("enabled", "enabled-runtime", "static", "linked"):
            callback(_empty_status())
            return

        service_launcher = Gio.SubprocessLauncher.new(
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
        )
        try:
            service_proc = service_launcher.spawnv([
                "flatpak-spawn", "--host", "systemctl", "show", SYSTEM_UPDATE_SERVICE,
                "--property=Result,ExecMainExitTimestamp",
            ])
        except GLib.Error:
            callback(_empty_status())
            return

        def on_service_done(service_source, service_result):
            try:
                _ok, service_stdout, _stderr = service_source.communicate_utf8_finish(service_result)
            except GLib.Error:
                callback(_empty_status())
                return
            service_props = _parse_show(service_stdout)
            exit_ts = service_props.get("ExecMainExitTimestamp", "")
            m = _DATE_RE.search(exit_ts)
            ran_today = bool(m) and m.group(0) == datetime.date.today().isoformat()
            result_str = service_props.get("Result")
            callback({
                "installed": True,
                "next_trigger": timer_props.get("NextElapseUSecRealtime") or None,
                "last_trigger": timer_props.get("LastTriggerUSec") or None,
                "last_result": result_str,
                "ran_today": ran_today,
                "succeeded_today": ran_today and result_str == "success",
            })

        service_proc.communicate_utf8_async(None, None, on_service_done)

    proc.communicate_utf8_async(None, None, on_timer_done)


def _empty_status():
    # Used both for "genuinely not installed" and for "couldn't query it"
    # (flatpak-spawn failing, an unreadable systemctl reply) — a real query
    # failure while it IS actually installed would misreport as "not set
    # up" here, but that's a reasonable degrade for a status display: no
    # false "everything's fine," and Enable is always safe to click again.
    return {
        "installed": False,
        "next_trigger": None, "last_trigger": None, "last_result": None,
        "ran_today": False, "succeeded_today": False,
    }


def _parse_show(stdout):
    props = {}
    for line in stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            props[k] = v
    return props


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
    try:
        service_content = (_DATA_DIR / SYSTEM_UPDATE_SERVICE).read_text()
        timer_content = (_DATA_DIR / SYSTEM_UPDATE_TIMER).read_text()
    except OSError as e:
        # Only reachable via a packaging bug (these ship as package data,
        # see pyproject.toml) — but callers only expect this function to
        # ever report failure through `callback`, never raise, so a bad
        # build shows a clean error instead of crashing the click handler.
        callback(False, f"couldn't read bundled unit files: {e}")
        return
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
