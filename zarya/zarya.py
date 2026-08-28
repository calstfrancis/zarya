import datetime
import json
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from . import backup_status, google_calendar, keyring, styles, weather
from .onboarding import OnboardingWindow
from .preferences import PreferencesWindow
from .weather_table import WeatherTable

APP_ID = "io.github.calstfrancis.zarya"

AUTOSTART_CONTENT = f"""[Desktop Entry]
Type=Application
Name=Zarya
Comment=Runs system and flatpak updates at login
Exec=flatpak run {APP_ID}
Icon={APP_ID}
X-Flatpak={APP_ID}
NoDisplay=true
"""


def marker_path() -> Path:
    return Path(GLib.get_user_cache_dir()) / "zarya" / "lastrun"


def result_path() -> Path:
    return Path(GLib.get_user_cache_dir()) / "zarya" / "lastresult.json"


def autostart_path() -> Path:
    return Path(GLib.get_user_config_dir()) / "autostart" / f"{APP_ID}.desktop"


def config_path() -> Path:
    return Path(GLib.get_user_config_dir()) / "zarya" / "config.json"


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config))


def load_result():
    path = result_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_result(success: bool) -> None:
    now = datetime.datetime.now()
    path = result_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "date": now.date().isoformat(),
        "success": success,
        "time": now.strftime("%H:%M"),
    }))


STATE_COLORS = {
    "ok": "success",
    "failed": "error",
    "running": "accent",
    "paused": "dim-label",
    "idle": "dim-label",
    "skipped": "dim-label",
}

STATE_LABELS = {
    "ok": "OK",
    "failed": "Failed",
    "running": "Running",
    "paused": "Paused",
    "idle": "Idle",
    "skipped": "Skipped",
}


class ZaryaWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Zarya")
        self.set_default_size(700, 780)

        self.proc = None
        self.weather_data = None
        self.config = load_config()

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self.menu_popover = Gtk.Popover()
        menu_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=2,
            margin_top=6, margin_bottom=6, margin_start=6, margin_end=6,
        )
        prefs_button = Gtk.Button(label="Preferences", has_frame=False)
        prefs_button.set_halign(Gtk.Align.FILL)
        prefs_button.get_child().set_halign(Gtk.Align.START)
        prefs_button.connect("clicked", self.on_preferences_clicked)
        menu_box.append(prefs_button)
        about_button = Gtk.Button(label="About Zarya", has_frame=False)
        about_button.set_halign(Gtk.Align.FILL)
        about_button.get_child().set_halign(Gtk.Align.START)
        about_button.connect("clicked", self.on_about_clicked)
        menu_box.append(about_button)
        self.menu_popover.set_child(menu_box)
        menu_button.set_popover(self.menu_popover)
        header.pack_end(menu_button)

        self.toast_overlay = Adw.ToastOverlay()

        root_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )

        self.status_label = Gtk.Label(xalign=0)
        self.status_label.add_css_class("title-4")
        root_box.append(self.status_label)

        result_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.result_icon = Gtk.Image()
        self.result_label = Gtk.Label(xalign=0)
        result_box.append(self.result_icon)
        result_box.append(self.result_label)
        root_box.append(result_box)

        # --- Weather ---
        weather_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        weather_content.add_css_class("fondwave-card")
        self.weather_summary_label = Gtk.Label(xalign=0, wrap=True)
        self.weather_summary_label.set_label("Set a location in Preferences to see today's weather.")
        weather_content.append(self.weather_summary_label)
        self.weather_table = WeatherTable()
        self.weather_table.set_visible(False)
        weather_content.append(self.weather_table)
        weather_expander, self.weather_status_icon = self._make_section(
            "weather", "Weather", weather_content, self.fetch_weather
        )
        root_box.append(weather_expander)

        # --- Backups ---
        self.backup_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        open_pereprava_button = Gtk.Button(icon_name="folder-remote-symbolic", has_frame=False)
        open_pereprava_button.set_tooltip_text("Open Pereprava")
        open_pereprava_button.connect("clicked", self.on_open_pereprava_clicked)
        backup_expander, self.backup_status_icon = self._make_section(
            "backups", "Backups", self.backup_box, self.fetch_backups,
            extra_button=open_pereprava_button,
        )
        root_box.append(backup_expander)

        # --- Today's events ---
        self.events_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        events_expander, self.events_status_icon = self._make_section(
            "events", "Today's Events", self.events_box, self.fetch_events
        )
        root_box.append(events_expander)

        # --- Update log ---
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_min_content_height(260)
        scrolled.add_css_class("card")
        scrolled.add_css_class("fondwave-terminal")
        self.text_view = Gtk.TextView(
            editable=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            top_margin=8,
            bottom_margin=8,
            left_margin=8,
            right_margin=8,
        )
        self.buffer = self.text_view.get_buffer()
        self.log_error_tag = self.buffer.create_tag("log-error", foreground=styles.TERMINAL_RED)
        self.log_success_tag = self.buffer.create_tag("log-success", foreground=styles.TERMINAL_GREEN)
        scrolled.set_child(self.text_view)
        root_box.append(scrolled)

        button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        autostart_label = Gtk.Label(label="Start at login")
        self.autostart_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.autostart_switch.set_active(autostart_path().exists())
        self.autostart_switch.connect("state-set", self.on_autostart_toggled)
        button_row.append(autostart_label)
        button_row.append(self.autostart_switch)

        spacer = Gtk.Box(hexpand=True)
        button_row.append(spacer)

        self.run_button = Gtk.Button(label="Run Now")
        self.run_button.add_css_class("suggested-action")
        self.run_button.connect("clicked", self.on_run_clicked)
        button_row.append(self.run_button)

        self.cancel_button = Gtk.Button(label="Cancel")
        self.cancel_button.set_sensitive(False)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)
        button_row.append(self.cancel_button)

        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda *_: self.close())
        button_row.append(close_button)

        root_box.append(button_row)

        self.toast_overlay.set_child(root_box)
        toolbar_view.set_content(self.toast_overlay)
        self.set_content(toolbar_view)

        self.refresh_status()
        if self.config.get("location"):
            self.fetch_weather()
        self.fetch_backups()
        if keyring.lookup_google_refresh_token():
            self.fetch_events()
        else:
            self._set_box_message(self.events_box, "Connect Google Calendar in Preferences to see today's events.")

    def _make_section(self, key, title, content, on_refresh, extra_button=None):
        status_icon = Gtk.Image()
        status_icon.set_pixel_size(16)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_label = Gtk.Label(label=title, xalign=0, hexpand=True)
        title_label.add_css_class("heading")
        header_box.append(title_label)
        header_box.append(status_icon)
        if extra_button is not None:
            header_box.append(extra_button)
        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", has_frame=False)
        refresh_button.set_tooltip_text(f"Refresh {title.lower()}")
        refresh_button.connect("clicked", lambda *_: on_refresh())
        header_box.append(refresh_button)

        expander = Gtk.Expander()
        expander.set_label_widget(header_box)
        expander.set_child(content)
        expander.set_expanded(self.config.get(f"{key}_expanded", True))
        expander.connect("notify::expanded", self._on_section_toggled, key)
        return expander, status_icon

    def _on_section_toggled(self, expander, _pspec, key):
        self.config[f"{key}_expanded"] = expander.get_expanded()
        save_config(self.config)

    @staticmethod
    def _set_status_icon(icon, kind):
        icon.remove_css_class("success")
        icon.remove_css_class("error")
        if kind == "ok":
            icon.set_from_icon_name("emblem-ok-symbolic")
            icon.add_css_class("success")
        elif kind == "error":
            icon.set_from_icon_name("dialog-error-symbolic")
            icon.add_css_class("error")
        else:
            icon.set_from_icon_name(None)

    # --- menu ---

    def on_preferences_clicked(self, _button):
        self.menu_popover.popdown()
        prefs = PreferencesWindow(
            self, self.config, save_config,
            on_weather_changed=self.fetch_weather,
            on_calendar_changed=self.fetch_events,
        )
        prefs.present()

    def on_about_clicked(self, _button):
        self.menu_popover.popdown()
        about = Adw.AboutWindow(
            transient_for=self,
            application_name="Zarya",
            application_icon=APP_ID,
            version="0.1.0-dev",
            developer_name="Praxis",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/calstfrancis/zarya",
        )
        about.present()

    # --- weather ---

    def fetch_weather(self):
        location = self.config.get("location", "").strip()
        if not location:
            self.weather_summary_label.set_label("Set a location in Preferences to see today's weather.")
            self.weather_table.set_visible(False)
            self._set_status_icon(self.weather_status_icon, "neutral")
            return
        self.weather_summary_label.set_label(f"Loading weather for {location}…")

        def worker():
            try:
                lat, lon, label = weather.geocode(location)
                today = weather.fetch_today(lat, lon)
                today["label"] = label
            except (OSError, ValueError, KeyError) as e:
                GLib.idle_add(self.on_weather_error, str(e))
                return
            GLib.idle_add(self.on_weather_ready, today)

        threading.Thread(target=worker, daemon=True).start()

    def on_weather_error(self, message):
        self.weather_summary_label.set_label(f"Couldn't get weather: {message}")
        self.weather_table.set_visible(False)
        self._set_status_icon(self.weather_status_icon, "error")
        return False

    def on_weather_ready(self, data):
        self.weather_data = data
        self.weather_table.set_visible(True)
        self._set_status_icon(self.weather_status_icon, "ok")
        self.render_weather()
        return False

    def render_weather(self):
        if not self.weather_data:
            return
        d = self.weather_data
        units = self.config.get("units", "celsius")
        if units == "fahrenheit":
            temps = [weather.celsius_to_fahrenheit(t) for t in d["temp_c"]]
            hi = round(weather.celsius_to_fahrenheit(d["temp_max_c"]))
            lo = round(weather.celsius_to_fahrenheit(d["temp_min_c"]))
            unit_letter = "F"
        else:
            temps = d["temp_c"]
            hi = round(d["temp_max_c"])
            lo = round(d["temp_min_c"])
            unit_letter = "C"
        desc = weather.describe(d["code"])
        self.weather_summary_label.set_label(f"{d['label']}: {desc}, {hi}°{unit_letter} / {lo}°{unit_letter}")
        self.weather_table.set_data(d["hours"], temps, d["humidity"], d["precip_prob"], unit_letter)

    # --- backups ---

    def on_open_pereprava_clicked(self, _button):
        try:
            Gio.Subprocess.new(
                ["flatpak-spawn", "--host", "pereprava"], Gio.SubprocessFlags.NONE
            )
        except GLib.Error as e:
            self.toast_overlay.add_toast(Adw.Toast(title=f"Couldn't open Pereprava: {e}"))

    def fetch_backups(self):
        self._set_box_message(self.backup_box, "Checking backup status…")
        backup_status.fetch_status(self.on_backup_status)

    def on_backup_status(self, jobs, error):
        if error is not None:
            self._set_box_message(self.backup_box, f"Couldn't check backup status: {error}")
            self._set_status_icon(self.backup_status_icon, "error")
            return
        if not jobs:
            self._set_box_message(self.backup_box, "No Pereprava jobs configured.")
            self._set_status_icon(self.backup_status_icon, "neutral")
            return
        any_failed = any(job.get("state") == "failed" for job in jobs)
        self._set_status_icon(self.backup_status_icon, "error" if any_failed else "ok")
        self._clear_box(self.backup_box)
        for job in jobs:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            name_label = Gtk.Label(label=job.get("name", "?"), xalign=0, hexpand=True)
            row.append(name_label)
            state = job.get("state", "idle")
            state_label = Gtk.Label(label=STATE_LABELS.get(state, state))
            state_label.add_css_class(STATE_COLORS.get(state, "dim-label"))
            row.append(state_label)
            last_run_text = self._format_backup_last_run(job)
            if last_run_text:
                last_run_label = Gtk.Label(label=last_run_text)
                last_run_label.add_css_class("dim-label")
                row.append(last_run_label)
            self.backup_box.append(row)

    @staticmethod
    def _format_backup_last_run(job):
        last_run = job.get("last_run")
        if isinstance(last_run, (int, float)) and last_run > 0:
            try:
                dt = datetime.datetime.fromtimestamp(last_run / 1_000_000)
                return dt.strftime("%Y-%m-%d %H:%M")
            except (OverflowError, OSError, ValueError):
                return None
        return job.get("last_run_text") or None

    # --- calendar ---

    def fetch_events(self):
        refresh_token = keyring.lookup_google_refresh_token()
        if not refresh_token:
            self._set_box_message(self.events_box, "Connect Google Calendar in Preferences to see today's events.")
            self._set_status_icon(self.events_status_icon, "neutral")
            return
        self._set_box_message(self.events_box, "Loading today's events…")

        def worker():
            try:
                events = google_calendar.fetch_today_events(refresh_token)
            except (OSError, ValueError, KeyError) as e:
                GLib.idle_add(self.on_events_error, str(e))
                return
            GLib.idle_add(self.on_events_ready, events)

        threading.Thread(target=worker, daemon=True).start()

    def on_events_error(self, message):
        self._set_box_message(self.events_box, f"Couldn't load events: {message}")
        self._set_status_icon(self.events_status_icon, "error")
        return False

    def on_events_ready(self, events):
        self._set_status_icon(self.events_status_icon, "ok")
        if not events:
            self._set_box_message(self.events_box, "No events today.")
            return False
        self._clear_box(self.events_box)
        for event in events:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            time_text = "All day" if event["all_day"] else event["start"].strftime("%I:%M %p").lstrip("0")
            time_label = Gtk.Label(label=time_text)
            time_label.add_css_class("dim-label")
            time_label.set_width_chars(8)
            time_label.set_xalign(0)
            row.append(time_label)
            summary_label = Gtk.Label(label=event["summary"], xalign=0, hexpand=True, wrap=True)
            row.append(summary_label)
            self.events_box.append(row)
        return False

    # --- shared helpers ---

    @staticmethod
    def _clear_box(box):
        child = box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            box.remove(child)
            child = next_child

    def _set_box_message(self, box, message):
        self._clear_box(box)
        box.append(Gtk.Label(label=message, xalign=0, wrap=True))

    def log(self, text):
        end = self.buffer.get_end_iter()
        self.buffer.insert(end, text)
        self.text_view.scroll_to_iter(self.buffer.get_end_iter(), 0.0, False, 0, 0)

    def logline(self, text):
        text = text.rstrip("\n") + "\n"
        start_offset = self.buffer.get_end_iter().get_offset()
        self.log(text)
        lower = text.lower()
        tag = None
        if "failed" in lower or "error" in lower or "cancelling" in lower:
            tag = self.log_error_tag
        elif "all done" in lower:
            tag = self.log_success_tag
        if tag is not None:
            start_iter = self.buffer.get_iter_at_offset(start_offset)
            self.buffer.apply_tag(tag, start_iter, self.buffer.get_end_iter())

    def today_str(self):
        return datetime.date.today().isoformat()

    def already_ran_today(self):
        path = marker_path()
        if not path.exists():
            return False
        return path.read_text().strip() == self.today_str()

    def mark_done(self):
        path = marker_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.today_str())

    def refresh_status(self):
        if self.already_ran_today():
            self.status_label.set_label("Already updated today")
            self.run_button.set_label("Run Anyway")
        else:
            self.status_label.set_label("Ready to update")
            self.run_button.set_label("Run Now")

        result = load_result()
        for css_class in ("success", "error"):
            self.result_label.remove_css_class(css_class)
        if result is None:
            self.result_icon.set_from_icon_name("dialog-question-symbolic")
            self.result_label.set_label("No update has run yet")
        elif result.get("success"):
            self.result_icon.set_from_icon_name("emblem-ok-symbolic")
            self.result_label.set_label(f"Last update succeeded at {result.get('time', '?')}")
            self.result_label.add_css_class("success")
        else:
            self.result_icon.set_from_icon_name("dialog-error-symbolic")
            self.result_label.set_label(f"Last update failed at {result.get('time', '?')}")
            self.result_label.add_css_class("error")

    def on_autostart_toggled(self, switch, state):
        path = autostart_path()
        try:
            if state:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(AUTOSTART_CONTENT)
            else:
                path.unlink(missing_ok=True)
        except OSError as e:
            self.toast_overlay.add_toast(Adw.Toast(title=f"Couldn't update autostart: {e}"))
            return True
        return False

    def on_run_clicked(self, _button):
        if self.proc is not None:
            return
        self.start_updates()

    def on_cancel_clicked(self, _button):
        if self.proc is None:
            return
        self.logline("")
        self.logline("--- cancelling… ---")
        try:
            self.proc.force_exit()
        except GLib.Error as e:
            self.logline(f"[cancel error: {e}]")

    def start_updates(self):
        if self.proc is not None:
            return
        self.buffer.set_text("")
        self.run_button.set_sensitive(False)
        self.cancel_button.set_sensitive(True)
        self.status_label.set_label("Updating…")
        self.logline(f"=== Zarya update: {self.today_str()} ===")
        self.logline("")
        self.logline("--- zypper refresh + dist-upgrade + system flatpaks (enter your password when prompted) ---")
        self.run_step(
            [
                "flatpak-spawn", "--host", "pkexec", "sh", "-c",
                "zypper ref && zypper dup -y && flatpak update --system -y",
            ],
            self.on_privileged_done,
        )

    def on_privileged_done(self, success, exit_status):
        self.logline("")
        if not success:
            self.logline(f"zypper/system-flatpak step failed (exit status {exit_status}).")
            self.finish(success=False)
            return
        self.logline("--- flatpak update (user installs) ---")
        self.run_step(
            ["flatpak-spawn", "--host", "flatpak", "update", "--user", "-y"],
            self.on_flatpak_done,
        )

    def on_flatpak_done(self, success, exit_status):
        self.logline("")
        if not success:
            self.logline(f"flatpak update failed (exit status {exit_status}).")
        self.finish(success=success)

    def finish(self, success):
        self.proc = None
        self.run_button.set_sensitive(True)
        self.cancel_button.set_sensitive(False)
        save_result(success)
        if success:
            self.mark_done()
            self.logline("All done.")
        else:
            self.logline("Not marking today as done — you can retry with Run Anyway.")
        self.refresh_status()

    def run_step(self, argv, done_callback):
        launcher = Gio.SubprocessLauncher.new(
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
        )
        try:
            self.proc = launcher.spawnv(argv)
        except GLib.Error as e:
            self.logline(f"Failed to start: {e}")
            self.finish(success=False)
            return

        # Completion is driven by the process actually exiting (wait_async),
        # not by the stdout pipe reaching EOF: zypper/rpm can fork a helper
        # (gpg-agent, etc.) that inherits the pipe's write end and keeps it
        # open well after the command we care about has finished, which would
        # otherwise leave the read loop waiting for an EOF that never comes.
        proc = self.proc
        stream = Gio.DataInputStream.new(proc.get_stdout_pipe())
        self._pump_output(stream)
        proc.wait_async(None, self._on_wait, done_callback)

    def _pump_output(self, stream):
        def on_line(source, result):
            try:
                line, _length = source.read_line_finish_utf8(result)
            except GLib.Error:
                return
            if line is None:
                return
            self.logline(line)
            source.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line)

        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line)

    def _on_wait(self, proc, result, done_callback):
        try:
            proc.wait_finish(result)
        except GLib.Error:
            pass
        success = proc.get_successful()
        exit_status = proc.get_exit_status()
        done_callback(success, exit_status)


class ZaryaApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.window = None

    def do_activate(self):
        first_launch = self.window is None
        if first_launch:
            styles.apply()
            self.window = ZaryaWindow(self)
        self.window.present()
        if first_launch:
            if self.window.config.get("onboarded"):
                if not self.window.already_ran_today():
                    GLib.idle_add(self.window.start_updates)
            else:
                onboarding = OnboardingWindow(
                    self.window, self.window.config, save_config,
                    on_finished=self.on_onboarding_finished,
                )
                onboarding.present()

    def on_onboarding_finished(self):
        self.window.fetch_weather()
        self.window.fetch_events()
        if not self.window.already_ran_today():
            GLib.idle_add(self.window.start_updates)


def main():
    app = ZaryaApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
