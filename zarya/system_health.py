import json

from gi.repository import Gio, GLib

# Disk usage needs the host's real filesystem (the sandbox's own "/" is the
# runtime image, not the host disk), so it goes through flatpak-spawn --host
# like everything else that needs host state. SMART health is different: it
# doesn't need a host command at all, since UDisks2 (which already runs on
# the host, outside any sandbox) exposes cached SMART properties over the
# system bus for any user to *read* — no root, no pkexec, unlike smartctl
# run directly, which needs raw device access. Verified this actually
# returns real data (a live NVMe drive's SmartCriticalWarning) before
# writing this module.

_DISK_USAGE_SCRIPT = r'''
import json
import os
import shutil

paths = ["/", os.path.expanduser("~")]
seen_totals = set()
results = []
for path in paths:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        continue
    # Dedup by capacity, not st_dev: btrfs subvolumes (openSUSE's default
    # layout puts /home on its own subvolume) report different st_dev for
    # the same underlying pool, so st_dev alone doesn't collapse them —
    # matching total bytes is a much more reliable signal they're the same
    # storage.
    if usage.total in seen_totals:
        continue
    seen_totals.add(usage.total)
    results.append({"path": path, "total": usage.total, "used": usage.used, "free": usage.free})
print(json.dumps(results))
'''

UDISKS_BUS_NAME = "org.freedesktop.UDisks2"
UDISKS_OBJECT_PATH = "/org/freedesktop/UDisks2"


def fetch_disk_usage(callback):
    """Runs asynchronously; callback(disks, error) on the main loop with
    exactly one of the two set."""
    launcher = Gio.SubprocessLauncher.new(
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
    )
    try:
        proc = launcher.spawnv(["flatpak-spawn", "--host", "python3", "-c", _DISK_USAGE_SCRIPT])
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
            disks = json.loads(stdout)
        except (json.JSONDecodeError, TypeError):
            callback(None, stdout.strip() or "no output from disk usage check")
            return
        callback(disks, None)

    proc.communicate_utf8_async(None, None, on_done)


def fetch_smart_health():
    """Synchronous — a single local system-bus call, fast enough to run
    directly; callers on a background thread if they want to be safe."""
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    result = bus.call_sync(
        UDISKS_BUS_NAME, UDISKS_OBJECT_PATH,
        "org.freedesktop.DBus.ObjectManager", "GetManagedObjects",
        None, None, Gio.DBusCallFlags.NONE, 10000, None,
    )
    (objects,) = result.unpack()

    drives = []
    for path, interfaces in objects.items():
        drive_props = interfaces.get("org.freedesktop.UDisks2.Drive")
        if not drive_props:
            continue
        model = (drive_props.get("Model") or "").strip() or path.rsplit("/", 1)[-1]

        ata = interfaces.get("org.freedesktop.UDisks2.Drive.Ata")
        nvme = interfaces.get("org.freedesktop.UDisks2.NVMe.Controller")
        if ata is not None:
            failing = bool(ata.get("SmartFailing"))
            drives.append({
                "model": model,
                "healthy": not failing,
                "detail": "SMART failing" if failing else "SMART OK",
            })
        elif nvme is not None:
            warnings = nvme.get("SmartCriticalWarning") or []
            healthy = not warnings
            drives.append({
                "model": model,
                "healthy": healthy,
                "detail": "SMART OK" if healthy else f"Critical warning: {', '.join(warnings)}",
            })
        # Drives with neither interface (USB flash, SD cards, some external
        # enclosures that don't pass SMART through) are skipped — nothing
        # meaningful to report.
    return drives
