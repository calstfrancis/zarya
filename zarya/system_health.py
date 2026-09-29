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

# Every real, block-device-backed filesystem mounted on the host — not just
# "/" and $HOME, which used to hide any extra drive (e.g. a SATA data disk
# mounted at /mnt/data). Pseudo filesystems, boot/EFI partitions, and
# container/package plumbing are skipped; multiple mounts of one device
# (btrfs subvolumes, bind mounts) collapse to a single entry.
REAL_FS = {
    "ext2", "ext3", "ext4", "xfs", "btrfs", "f2fs", "zfs", "jfs", "reiserfs",
    "ntfs", "ntfs3", "fuseblk", "exfat", "vfat", "hfsplus",
}
SKIP_PREFIXES = ("/boot", "/efi", "/run", "/snap", "/var/lib", "/sys", "/proc", "/dev", "/tmp")

def unescape(s):
    return s.replace("\\040", " ").replace("\\011", "\t").replace("\\134", "\\")

home = os.path.realpath(os.path.expanduser("~"))
mounts = []
try:
    with open("/proc/self/mounts") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            source, mountpoint, fstype = parts[0], unescape(parts[1]), parts[2]
            if fstype not in REAL_FS or not source.startswith("/dev/"):
                continue
            if mountpoint != "/" and mountpoint.startswith(SKIP_PREFIXES):
                continue
            mounts.append((source, mountpoint))
except OSError:
    pass

home_mount = "/"
for _src, mp in mounts:
    if (home == mp or home.startswith(mp.rstrip("/") + "/")) and len(mp) > len(home_mount):
        home_mount = mp

by_device = {}
for source, mountpoint in mounts:
    current = by_device.get(source)
    if current is None or len(mountpoint) < len(current):
        by_device[source] = mountpoint

results = []
seen = set()
for source, mountpoint in by_device.items():
    try:
        usage = shutil.disk_usage(mountpoint)
    except OSError:
        continue
    if usage.total <= 0:
        continue
    # Same capacity + same usage across different device nodes is one pool
    # seen through several nodes (btrfs multi-device / subvolume mounts).
    key = (usage.total, usage.used)
    if key in seen:
        continue
    seen.add(key)
    if mountpoint == "/":
        label = "System ( / )"
    elif mountpoint == home_mount:
        label = "Home"
    else:
        label = os.path.basename(mountpoint.rstrip("/")) or mountpoint
    results.append({"path": mountpoint, "label": label, "total": usage.total, "used": usage.used, "free": usage.free})
results.sort(key=lambda r: (r["path"] != "/", r["label"] != "Home", r["path"]))
print(json.dumps(results))
'''

_THERMAL_SCRIPT = r'''
import glob
import json
import os

# Only chips that are actually CPU/GPU dies — hwmon also exposes battery,
# NVMe (already covered by drive SMART), Wi-Fi radios, AC adapters, etc.,
# which would just be noise here.
CPU_CHIPS = {"k10temp", "coretemp", "zenpower", "zenpower3"}
GPU_CHIPS = {"amdgpu", "nouveau", "i915", "xe"}
PREFERRED_LABELS = ("tctl", "tdie", "package", "edge")

results = []
for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
    try:
        with open(os.path.join(hwmon, "name")) as f:
            name = f.read().strip()
    except OSError:
        continue
    if name not in CPU_CHIPS and name not in GPU_CHIPS:
        continue

    readings = []
    for temp_input in sorted(glob.glob(os.path.join(hwmon, "temp*_input"))):
        try:
            with open(temp_input) as f:
                milli_c = int(f.read().strip())
        except (OSError, ValueError):
            continue
        label = None
        label_path = temp_input.replace("_input", "_label")
        if os.path.exists(label_path):
            try:
                with open(label_path) as f:
                    label = f.read().strip()
            except OSError:
                pass
        readings.append((label or "", milli_c / 1000.0))

    if not readings:
        continue
    # Prefer the canonical "package"/"die" sensor over individual per-core
    # readings if the chip exposes one; otherwise just take the hottest.
    preferred = [r for r in readings if r[0].lower() in PREFERRED_LABELS]
    label, celsius = (preferred[0] if preferred else max(readings, key=lambda r: r[1]))
    results.append({
        "chip": name,
        "kind": "cpu" if name in CPU_CHIPS else "gpu",
        "label": label or name,
        "celsius": celsius,
    })

print(json.dumps(results))
'''

UDISKS_BUS_NAME = "org.freedesktop.UDisks2"
UDISKS_OBJECT_PATH = "/org/freedesktop/UDisks2"

UPOWER_BUS_NAME = "org.freedesktop.UPower"
UPOWER_OBJECT_PATH = "/org/freedesktop/UPower"
UPOWER_DEVICE_IFACE = "org.freedesktop.UPower.Device"
UPOWER_TYPE_BATTERY = 2


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


def fetch_thermal_health(callback):
    """Runs asynchronously; callback(readings, error) on the main loop.
    Needs flatpak-spawn --host like disk usage — /sys/class/hwmon inside
    the sandbox isn't guaranteed to reflect the host's real sensors."""
    launcher = Gio.SubprocessLauncher.new(
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
    )
    try:
        proc = launcher.spawnv(["flatpak-spawn", "--host", "python3", "-c", _THERMAL_SCRIPT])
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
            readings = json.loads(stdout)
        except (json.JSONDecodeError, TypeError):
            callback(None, stdout.strip() or "no output from thermal check")
            return
        callback(readings, None)

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


def fetch_battery_health():
    """Same treatment as fetch_smart_health(): UPower already runs as root
    on the host and exposes battery wear (Capacity — verified this equals
    EnergyFull/EnergyFullDesign already, no need to compute it) read-only
    over the system bus. Returns [] on desktops with no battery, not an
    error — that's a normal, common case, not a failure."""
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    result = bus.call_sync(
        UPOWER_BUS_NAME, UPOWER_OBJECT_PATH, UPOWER_BUS_NAME, "EnumerateDevices",
        None, None, Gio.DBusCallFlags.NONE, 10000, None,
    )
    (paths,) = result.unpack()

    batteries = []
    for path in paths:
        props_result = bus.call_sync(
            UPOWER_BUS_NAME, path, "org.freedesktop.DBus.Properties", "GetAll",
            GLib.Variant("(s)", (UPOWER_DEVICE_IFACE,)),
            None, Gio.DBusCallFlags.NONE, 10000, None,
        )
        (props,) = props_result.unpack()
        if props.get("Type") != UPOWER_TYPE_BATTERY or not props.get("IsPresent"):
            continue
        batteries.append({
            "model": props.get("Model") or "Battery",
            "capacity": props.get("Capacity"),
            "percentage": props.get("Percentage"),
            "cycles": props.get("ChargeCycles"),
        })
    return batteries
