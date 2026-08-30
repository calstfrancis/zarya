import html
import json
import urllib.parse
import urllib.request

from .google_calendar import get_access_token

TASKS_URL = "https://www.googleapis.com/tasks/v1/lists/@default/tasks"


def _request(method, url, refresh_token, body=None):
    access_token = get_access_token(refresh_token)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {access_token}")
    if data is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else {}


def list_tasks(refresh_token):
    params = {"showCompleted": "true", "showHidden": "true", "maxResults": "100"}
    url = f"{TASKS_URL}?{urllib.parse.urlencode(params)}"
    data = _request("GET", url, refresh_token)
    tasks = [
        {"id": item["id"], "text": html.unescape(item.get("title", "")), "done": item.get("status") == "completed"}
        for item in data.get("items", [])
        if item.get("title")
    ]
    tasks.sort(key=lambda t: (t["done"], t["text"].lower()))
    return tasks


def add_task(refresh_token, text):
    data = _request("POST", TASKS_URL, refresh_token, {"title": text})
    return {"id": data["id"], "text": data.get("title", text), "done": False}


def set_task_done(refresh_token, task_id, done):
    url = f"{TASKS_URL}/{urllib.parse.quote(task_id, safe='')}"
    body = {"status": "completed" if done else "needsAction"}
    _request("PATCH", url, refresh_token, body)


def delete_task(refresh_token, task_id):
    url = f"{TASKS_URL}/{urllib.parse.quote(task_id, safe='')}"
    _request("DELETE", url, refresh_token)
