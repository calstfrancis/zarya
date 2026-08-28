import datetime
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

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


class ZaryaWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Zarya")
        self.set_default_size(640, 440)

        self.proc = None

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

        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda *_: self.close())
        button_row.append(close_button)

        root_box.append(button_row)

        self.toast_overlay.set_child(root_box)
        toolbar_view.set_content(self.toast_overlay)
        self.set_content(toolbar_view)

        self.refresh_status()

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

    def start_updates(self):
        if self.proc is not None:
            return
        self.buffer.set_text("")
        self.run_button.set_sensitive(False)
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

        stream = Gio.DataInputStream.new(self.proc.get_stdout_pipe())
        self._pump_output(stream, done_callback)

    def _pump_output(self, stream, done_callback):
        def on_line(source, result):
            try:
                line, _length = source.read_line_finish_utf8(result)
            except GLib.Error as e:
                self.logline(f"[read error: {e}]")
                line = None
            if line is None:
                self.proc.wait_async(None, self._on_wait, done_callback)
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
