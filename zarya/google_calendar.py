import base64
import datetime
import hashlib
import http.server
import json
import os
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request

from gi.repository import Gio, GLib

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/tasks"

# From the Google Cloud OAuth client (type "Desktop app") set up for Zarya.
# Not secret in the confidential sense — Google issues a client_secret even
# for installed-app clients, but it's shipped in the app like the client_id.
CLIENT_ID = "916752950525-m2lhrveifvecr271kfj33r61rpvkgup9.apps.googleusercontent.com"
CLIENT_SECRET = "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"


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        self.server.oauth_result = {
            "code": params.get("code", [None])[0],
            "state": params.get("state", [None])[0],
            "error": params.get("error", [None])[0],
        }
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body>Zarya: you can close this tab now.</body></html>")

    def log_message(self, *_args):
        pass


def _make_pkce_pair():
    verifier = base64.urlsafe_b64encode(os.urandom(40)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def connect(on_done):
    """Runs the OAuth loopback flow in the background. on_done(refresh_token,
    error) is invoked on the main loop with exactly one of the two set."""
    verifier, challenge = _make_pkce_pair()
    state = secrets.token_urlsafe(16)

    server = http.server.HTTPServer(("127.0.0.1", 0), _CallbackHandler)
    server.oauth_result = None
    server.timeout = 180
    port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    Gio.AppInfo.launch_default_for_uri(auth_url, None)

    def worker():
        server.handle_request()
        result = server.oauth_result
        server.server_close()
        if not result or result.get("error"):
            GLib.idle_add(on_done, None, (result or {}).get("error") or "no response from browser")
            return
        if result.get("state") != state:
            GLib.idle_add(on_done, None, "state mismatch (possible CSRF) — try connecting again")
            return
        code = result.get("code")
        if not code:
            GLib.idle_add(on_done, None, "no authorization code received")
            return
        try:
            refresh_token = _exchange_code(code, verifier, redirect_uri)
        except (OSError, ValueError, KeyError) as e:
            GLib.idle_add(on_done, None, str(e))
            return
        GLib.idle_add(on_done, refresh_token, None)

    threading.Thread(target=worker, daemon=True).start()


def _post_form(url, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def _exchange_code(code, verifier, redirect_uri):
    result = _post_form(TOKEN_URL, {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    })
    refresh_token = result.get("refresh_token")
    if not refresh_token:
        raise ValueError("Google didn't return a refresh token — try disconnecting and reconnecting")
    return refresh_token


def get_access_token(refresh_token):
    result = _post_form(TOKEN_URL, {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })
    access_token = result.get("access_token")
    if not access_token:
        raise ValueError("Couldn't refresh Google access token")
    return access_token


def _parse_rfc3339(value):
    if not value:
        return None
    return datetime.datetime.fromisoformat(value).astimezone().replace(tzinfo=None)


def list_calendars(refresh_token):
    access_token = get_access_token(refresh_token)
    req = urllib.request.Request(CALENDAR_LIST_URL)
    req.add_header("Authorization", f"Bearer {access_token}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    calendars = [
        {
            "id": item["id"],
            "summary": item.get("summary", item["id"]),
            "primary": item.get("primary", False),
        }
        for item in data.get("items", [])
    ]
    calendars.sort(key=lambda c: (not c["primary"], c["summary"].lower()))
    return calendars


def fetch_today_events(refresh_token, calendar_ids=None):
    if not calendar_ids:
        calendar_ids = ["primary"]
    access_token = get_access_token(refresh_token)
    today = datetime.date.today()
    time_min = datetime.datetime.combine(today, datetime.time.min).astimezone().isoformat()
    time_max = datetime.datetime.combine(today, datetime.time.max).astimezone().isoformat()
    params = {
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": "true",
        "orderBy": "startTime",
    }

    events = []
    for calendar_id in calendar_ids:
        events_url = f"https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(calendar_id, safe='')}/events"
        url = f"{events_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {access_token}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError:
            # A calendar that's since been removed/unshared, etc. — skip it
            # rather than failing the whole fetch over one bad calendar.
            continue

        for item in data.get("items", []):
            start_info = item.get("start", {})
            end_info = item.get("end", {})
            if "date" in start_info:
                start = datetime.datetime.strptime(start_info["date"], "%Y-%m-%d")
                all_day = True
            else:
                start = _parse_rfc3339(start_info.get("dateTime"))
                all_day = False
            end = _parse_rfc3339(end_info.get("dateTime")) if "dateTime" in end_info else None
            events.append({
                "summary": item.get("summary", "(untitled)"),
                "start": start,
                "end": end,
                "all_day": all_day,
            })
    events.sort(key=lambda e: e["start"])
    return events
