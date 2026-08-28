import json

from gi.repository import Gio, GLib

# Runs on the host (via flatpak-spawn --host) because the job definitions and
# systemd --user units live there, not in the sandbox — mirrors how Pereprava's
# own logic/status.py reads things, just re-run as a single embedded script so
# Zarya doesn't need its own --filesystem grant into ~/.config/pereprava.
_STATUS_SCRIPT = r'''
import json
import subprocess
from pathlib import Path

jobs_dir = Path.home() / ".config" / "pereprava" / "jobs"
results = []


def show(unit, props):
    try:
        out = subprocess.run(
            ["systemctl", "--user", "show", unit, "--property=" + ",".join(props)],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        return {}
    d = {}
    for line in out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            d[k] = v
    return d


def last_timer_run(timer_unit):
    try:
        out = subprocess.run(
            ["systemctl", "--user", "list-timers", timer_unit, "--output=json"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        timers = json.loads(out) if out.strip() else []
    except Exception:
        return None
    if not timers:
        return None
    entry = timers[0]
    return entry.get("last") or entry.get("last_usec") or entry.get("last_trigger_usec")


if jobs_dir.exists():
    for f in sorted(jobs_dir.glob("*.json")):
        try:
            job = json.loads(f.read_text())
        except Exception:
            continue
        slug = job.get("slug") or f.stem
        name = job.get("name", slug)
        job_type = job.get("job_type", "")
        unit = f"pereprava-job-{slug}"
        service = f"{unit}.service"
        timer = f"{unit}.timer"

        if job_type == "rclone_mount":
            props = show(service, ["ActiveState", "Result", "UnitFileState", "ActiveEnterTimestamp"])
            enabled = props.get("UnitFileState") == "enabled"
            active = props.get("ActiveState", "")
            result = props.get("Result", "")
            if not enabled:
                state = "paused"
            elif active == "failed" or (result and result != "success"):
                state = "failed"
            elif active == "active":
                state = "ok"
            else:
                state = "idle"
            last_run = None
            last_run_text = props.get("ActiveEnterTimestamp") or None
        else:
            props = show(service, ["ActiveState", "Result"])
            timer_props = show(timer, ["UnitFileState"])
            enabled = timer_props.get("UnitFileState") == "enabled"
            result = props.get("Result", "")
            active = props.get("ActiveState", "")
            last_run = last_timer_run(timer)
            last_run_text = None
            if active in ("activating", "reloading"):
                state = "running"
            elif not enabled:
                state = "paused"
            elif not result:
                state = "idle"
            elif result == "success":
                state = "ok"
            else:
                state = "failed"

        results.append({
            "name": name,
            "state": state,
            "result": result,
            "last_run": last_run,
            "last_run_text": last_run_text,
        })

print(json.dumps(results))
'''


def fetch_status(callback):
    """Runs asynchronously; callback(jobs, error) is invoked on the main loop
    with exactly one of the two set."""
    launcher = Gio.SubprocessLauncher.new(
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
    )
    try:
        proc = launcher.spawnv(["flatpak-spawn", "--host", "python3", "-c", _STATUS_SCRIPT])
    except GLib.Error as e:
        callback(None, str(e))
        return

    def on_done(source, result):
        try:
            _ok, stdout, _stderr = source.communicate_utf8_finish(result)
        except GLib.Error as e:
            callback(None, str(e))
            return
        try:
            jobs = json.loads(stdout)
        except (json.JSONDecodeError, TypeError):
            callback(None, stdout.strip() or "no output from status check")
            return
        callback(jobs, None)

    proc.communicate_utf8_async(None, None, on_done)
