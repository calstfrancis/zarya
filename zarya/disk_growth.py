import datetime
import json
from pathlib import Path

from gi.repository import Gio, GLib

# Sizes of each top-level (non-hidden) directory directly under the host's
# real home — needs flatpak-spawn --host for the same reason as
# system_health's disk usage check: the sandbox's own view of "~" isn't the
# host's real home. `du` (not a Python os.walk) because it's the host's own
# C binary walking a potentially large tree — much cheaper than doing the
# same walk over a flatpak-spawn round trip in Python.
_DU_SCRIPT = 'du -sb -- "$HOME"/*/ 2>/dev/null'

HISTORY_LIMIT_DAYS = 40
COMPARE_AFTER_DAYS = 7


def history_path() -> Path:
    return Path(GLib.get_user_cache_dir()) / "zarya" / "disk_growth_history.json"


def load_history() -> list:
    path = history_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []


def save_history(history: list) -> None:
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history))


def record_snapshot(sizes: dict) -> list:
    """Adds/overwrites today's entry in the on-disk history and prunes
    anything older than HISTORY_LIMIT_DAYS, returning the updated history."""
    today = datetime.date.today().isoformat()
    history = [h for h in load_history() if h.get("date") != today]
    history.append({"date": today, "sizes": sizes})
    cutoff = (datetime.date.today() - datetime.timedelta(days=HISTORY_LIMIT_DAYS)).isoformat()
    history = [h for h in history if h.get("date", "") >= cutoff]
    history.sort(key=lambda h: h.get("date", ""))
    save_history(history)
    return history


def growth_since(history: list, sizes: dict) -> tuple[list, bool]:
    """Returns (rows, has_baseline). Each row is
    (name, current_bytes, delta_bytes), sorted by growth descending.
    `has_baseline` is False if no snapshot old enough to compare against
    exists yet (first week of history)."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=COMPARE_AFTER_DAYS)).isoformat()
    baseline_entries = [h for h in history if h.get("date", "") <= cutoff]
    if not baseline_entries:
        return [], False
    baseline = baseline_entries[-1]["sizes"]  # closest to (but not more recent than) 7 days ago

    rows = []
    for name, current in sizes.items():
        delta = current - baseline.get(name, current)
        rows.append((name, current, delta))
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows, True


def fetch_sizes(callback):
    """Runs asynchronously; callback(sizes: dict[str, int] | None, error)."""
    launcher = Gio.SubprocessLauncher.new(
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
    )
    try:
        proc = launcher.spawnv(["flatpak-spawn", "--host", "sh", "-c", _DU_SCRIPT])
    except GLib.Error as e:
        callback(None, str(e))
        return

    def on_done(source, result):
        try:
            _ok, stdout, _stderr = source.communicate_utf8_finish(result)
        except GLib.Error as e:
            callback(None, str(e))
            return
        sizes = {}
        for line in stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            size_str, path = parts
            try:
                size = int(size_str)
            except ValueError:
                continue
            name = path.rstrip("/").rsplit("/", 1)[-1]
            sizes[name] = size
        callback(sizes, None)

    proc.communicate_utf8_async(None, None, on_done)
