import base64
import datetime
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NS = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav"}


def _request(url, method, username, password, body=None, headers=None):
    data = body.encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Content-Type", "application/xml; charset=utf-8")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read()


def _calendar_home(server, username):
    return f"https://{server}/remote.php/dav/calendars/{username}/"


def discover_calendars(server, username, password):
    home = _calendar_home(server, username)
    home_path = urllib.parse.urlparse(home).path.rstrip("/")
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/></d:prop></d:propfind>'
    )
    data = _request(home, "PROPFIND", username, password, body, {"Depth": "1"})
    root = ET.fromstring(data)
    hrefs = []
    for response in root.findall("d:response", NS):
        href_el = response.find("d:href", NS)
        if href_el is None or not href_el.text:
            continue
        href = href_el.text
        if href.rstrip("/") == home_path:
            continue
        resourcetype = response.find(".//d:resourcetype", NS)
        if resourcetype is not None and resourcetype.find("c:calendar", NS) is not None:
            hrefs.append(href)
    return hrefs


def fetch_today_events(server, username, password):
    calendars = discover_calendars(server, username, password)
    today = datetime.date.today()
    start_str = today.strftime("%Y%m%dT000000Z")
    end_str = (today + datetime.timedelta(days=1)).strftime("%Y%m%dT000000Z")

    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
        "<d:prop><c:calendar-data>"
        f'<c:expand start="{start_str}" end="{end_str}"/>'
        "</c:calendar-data></d:prop>"
        "<c:filter><c:comp-filter name=\"VCALENDAR\"><c:comp-filter name=\"VEVENT\">"
        f'<c:time-range start="{start_str}" end="{end_str}"/>'
        "</c:comp-filter></c:comp-filter></c:filter>"
        "</c:calendar-query>"
    )

    events = []
    for href in calendars:
        url = urllib.parse.urljoin(f"https://{server}/", href.lstrip("/"))
        try:
            data = _request(url, "REPORT", username, password, body, {"Depth": "1"})
        except (OSError, ET.ParseError):
            continue
        root = ET.fromstring(data)
        for response in root.findall("d:response", NS):
            cdata = response.find(".//c:calendar-data", NS)
            if cdata is None or not cdata.text:
                continue
            events.extend(_parse_vevents(cdata.text))

    events.sort(key=lambda e: e["start"])
    return events


def _field(block, name):
    match = re.search(rf"^{name}(?:;[^:\n]*)?:(.*)$", block, re.M)
    return match.group(1).strip() if match else None


def _parse_ical_time(value):
    if not value:
        return None
    value = value.strip()
    try:
        if len(value) == 8:
            return datetime.datetime.strptime(value, "%Y%m%d")
        if value.endswith("Z"):
            dt = datetime.datetime.strptime(value, "%Y%m%dT%H%M%SZ")
            return dt.replace(tzinfo=datetime.timezone.utc).astimezone().replace(tzinfo=None)
        return datetime.datetime.strptime(value, "%Y%m%dT%H%M%S")
    except ValueError:
        return None


def _parse_vevents(ics_text):
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics_text, re.S):
        dtstart_raw = _field(block, "DTSTART")
        start = _parse_ical_time(dtstart_raw)
        if start is None:
            continue
        end = _parse_ical_time(_field(block, "DTEND"))
        all_day = bool(dtstart_raw) and len(dtstart_raw.strip()) == 8
        events.append({
            "summary": _field(block, "SUMMARY") or "(untitled)",
            "start": start,
            "end": end,
            "all_day": all_day,
        })
    return events
