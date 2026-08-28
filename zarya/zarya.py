import datetime
import json
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from . import weather
from .weather_chart import WeatherChart

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


class ZaryaWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Zarya")
        self.set_default_size(640, 440)

        self.proc = None
        self.weather_data = None
        self.config = load_config()

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        self.toast_overlay = Adw.ToastOverlay()

        root_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )

        self.status_label = Gtk.Label(xalign=0)
        self.status_label.add_css_class("title-4")
        root_box.append(self.status_label)

        weather_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.weather_summary_label = Gtk.Label(xalign=0, hexpand=True, wrap=True)
        self.weather_summary_label.set_label("Set a location to see today's weather.")
        weather_header.append(self.weather_summary_label)

        self.location_entry = Gtk.Entry(placeholder_text="City, Country")
        self.location_entry.set_size_request(180, -1)
        if self.config.get("location"):
            self.location_entry.set_text(self.config["location"])
        self.location_entry.connect("activate", self.on_location_activate)
        weather_header.append(self.location_entry)

        self.units_button = Gtk.Button(
            label="°F" if self.config.get("units", "fahrenheit") == "fahrenheit" else "°C"
        )
        self.units_button.connect("clicked", self.on_units_clicked)
        weather_header.append(self.units_button)

        weather_refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        weather_refresh_button.set_tooltip_text("Refresh weather")
        weather_refresh_button.connect("clicked", lambda *_: self.fetch_weather())
        weather_header.append(weather_refresh_button)

        root_box.append(weather_header)

        self.weather_chart = WeatherChart()
        self.weather_chart.set_visible(False)
        root_box.append(self.weather_chart)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.add_css_class("card")
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

    def on_location_activate(self, entry):
        location = entry.get_text().strip()
        if not location:
            return
        self.config["location"] = location
        save_config(self.config)
        self.fetch_weather()

    def on_units_clicked(self, button):
        current = self.config.get("units", "fahrenheit")
        new_units = "celsius" if current == "fahrenheit" else "fahrenheit"
        self.config["units"] = new_units
        save_config(self.config)
        button.set_label("°F" if new_units == "fahrenheit" else "°C")
        self.render_weather()

    def fetch_weather(self):
        location = self.config.get("location", "").strip()
        if not location:
            self.weather_summary_label.set_label("Set a location to see today's weather.")
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
        self.weather_chart.set_visible(False)
        return False

    def on_weather_ready(self, data):
        self.weather_data = data
        self.weather_chart.set_visible(True)
        self.render_weather()
        return False

    def render_weather(self):
        if not self.weather_data:
            return
        d = self.weather_data
        units = self.config.get("units", "fahrenheit")
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
        self.weather_chart.set_data(d["hours"], temps, d["humidity"], d["precip_prob"], unit_letter)

    def log(self, text):
        end = self.buffer.get_end_iter()
        self.buffer.insert(end, text)
        self.text_view.scroll_to_iter(self.buffer.get_end_iter(), 0.0, False, 0, 0)

    def logline(self, text):
        self.log(text.rstrip("\n") + "\n")

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
        self.logline("--- zypper refresh + dist-upgrade (enter your password when prompted) ---")
        self.run_step(
            ["flatpak-spawn", "--host", "pkexec", "sh", "-c", "zypper ref && zypper dup -y"],
            self.on_zypper_done,
        )

    def on_zypper_done(self, success, exit_status):
        self.logline("")
        if not success:
            self.logline(f"zypper step failed (exit status {exit_status}).")
            self.finish(success=False)
            return
        self.logline("--- flatpak update ---")
        self.run_step(
            ["flatpak-spawn", "--host", "flatpak", "update", "-y"],
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
            self.window = ZaryaWindow(self)
        self.window.present()
        if first_launch and not self.window.already_ran_today():
            GLib.idle_add(self.window.start_updates)


def main():
    app = ZaryaApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
