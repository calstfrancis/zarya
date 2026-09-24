import datetime
import json
from pathlib import Path

from gi.repository import GLib

# Durable data, not disposable cache (unlike history.json/disk_growth's
# history) — a habit log is exactly the kind of thing losing would actually
# hurt, so it lives under XDG_DATA_HOME like the rest of the suite's real
# data, not XDG_CACHE_HOME.


def data_path() -> Path:
    return Path(GLib.get_user_data_dir()) / "zarya" / "habits.json"


def load() -> dict:
    path = data_path()
    if not path.exists():
        return {"habits": [], "log": {}}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"habits": [], "log": {}}
    data.setdefault("habits", [])
    data.setdefault("log", {})
    return data


def save(data: dict) -> None:
    path = data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def add_habit(data: dict, name: str) -> None:
    name = name.strip()
    if name and name not in data["habits"]:
        data["habits"].append(name)
        save(data)


def remove_habit(data: dict, name: str) -> None:
    if name in data["habits"]:
        data["habits"].remove(name)
    data["log"].pop(name, None)
    save(data)


def is_done_today(data: dict, name: str) -> bool:
    today = datetime.date.today().isoformat()
    return today in data["log"].get(name, [])


def toggle_today(data: dict, name: str) -> None:
    today = datetime.date.today().isoformat()
    dates = data["log"].setdefault(name, [])
    if today in dates:
        dates.remove(today)
    else:
        dates.append(today)
    save(data)


def week_count(data: dict, name: str) -> int:
    """How many of the last 7 days (today back to 6 days ago) are marked
    done — a rolling window, not calendar-week-aligned, so it reads the
    same regardless of what day of the week it is."""
    dates = set(data["log"].get(name, []))
    today = datetime.date.today()
    return sum(
        1 for i in range(7) if (today - datetime.timedelta(days=i)).isoformat() in dates
    )


def current_streak(data: dict, name: str) -> int:
    """Consecutive days up to and including today, or up to yesterday if
    today isn't marked done yet — so the streak doesn't drop to zero the
    moment a new day starts, only once a full day is actually missed."""
    dates = set(data["log"].get(name, []))
    day = datetime.date.today()
    if day.isoformat() not in dates:
        day -= datetime.timedelta(days=1)
    streak = 0
    while day.isoformat() in dates:
        streak += 1
        day -= datetime.timedelta(days=1)
    return streak
