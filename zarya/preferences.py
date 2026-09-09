import threading

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk

from . import google_calendar, keyring, system_updates


class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, parent, config, save_config, on_weather_changed, on_units_changed, on_google_changed):
        super().__init__(transient_for=parent, modal=True)
        self.config = config
        self.save_config = save_config
        self.on_weather_changed = on_weather_changed
        self.on_units_changed = on_units_changed
        self.on_google_changed = on_google_changed

        weather_page = Adw.PreferencesPage(title="Weather", icon_name="weather-clear-symbolic")
        weather_group = Adw.PreferencesGroup(title="Location")

        self.location_row = Adw.EntryRow(title="City, Country")
        if config.get("location"):
            self.location_row.set_text(config["location"])
        weather_group.add(self.location_row)

        self.units_row = Adw.ComboRow(title="Units")
        self.units_row.set_model(Gtk.StringList.new(["Celsius", "Fahrenheit"]))
        self.units_row.set_selected(0 if config.get("units", "celsius") == "celsius" else 1)
        weather_group.add(self.units_row)

        weather_save_button = Gtk.Button(label="Save", halign=Gtk.Align.END)
        weather_save_button.add_css_class("suggested-action")
        weather_save_button.connect("clicked", self.on_weather_save)
        weather_group.add(weather_save_button)

        weather_page.add(weather_group)
        self.add(weather_page)

        calendar_page = Adw.PreferencesPage(title="Google", icon_name="x-office-calendar-symbolic")
        calendar_group = Adw.PreferencesGroup(
            title="Google Account",
            description="Opens your browser to sign in. Covers both today's Calendar events and the to-do sidebar (Google Tasks). The refresh token is stored in the system keyring, never the password.",
        )

        self.calendar_status_label = Gtk.Label(xalign=0, wrap=True)
        calendar_group.add(self.calendar_status_label)

        calendar_button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        self.connect_button = Gtk.Button(label="Connect Google Account")
        self.connect_button.add_css_class("suggested-action")
        self.connect_button.connect("clicked", self.on_connect_clicked)
        calendar_button_row.append(self.connect_button)

        self.disconnect_button = Gtk.Button(label="Disconnect")
        self.disconnect_button.connect("clicked", self.on_disconnect_clicked)
        calendar_button_row.append(self.disconnect_button)

        calendar_group.add(calendar_button_row)

        calendar_page.add(calendar_group)

        self.calendars_group = Adw.PreferencesGroup(
            title="Calendars",
            description="Choose which calendars show up in Today's Events.",
        )
        self.calendars_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.calendars_group.add(self.calendars_box)
        calendar_page.add(self.calendars_group)

        self.add(calendar_page)

        updates_page = Adw.PreferencesPage(title="Updates", icon_name="software-update-available-symbolic")
        updates_group = Adw.PreferencesGroup(
            title="Unattended Daily Updates",
            description=(
                "Runs zypper + the system flatpak update on their own, once a day, "
                "with no password prompt — via a root-owned systemd timer, set up "
                "with one password prompt now. “Run Now” in the main window "
                "is unaffected and still prompts every time, since that's a manual "
                "action you're present for, not the unattended case this is about."
            ),
        )

        self.updates_status_label = Gtk.Label(xalign=0, wrap=True)
        updates_group.add(self.updates_status_label)

        updates_button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        self.updates_enable_button = Gtk.Button(label="Enable")
        self.updates_enable_button.add_css_class("suggested-action")
        self.updates_enable_button.connect("clicked", self.on_updates_enable_clicked)
        updates_button_row.append(self.updates_enable_button)

        self.updates_disable_button = Gtk.Button(label="Disable")
        self.updates_disable_button.connect("clicked", self.on_updates_disable_clicked)
        updates_button_row.append(self.updates_disable_button)

        updates_group.add(updates_button_row)
        updates_page.add(updates_group)
        self.add(updates_page)

        self._refresh_calendar_status()
        self._refresh_calendars_list()
        self._refresh_updates_status()

    def _refresh_calendar_status(self):
        connected = bool(keyring.lookup_google_refresh_token())
        self.calendar_status_label.set_label("Connected." if connected else "Not connected.")
        self.disconnect_button.set_sensitive(connected)

    def on_connect_clicked(self, _button):
        self.connect_button.set_sensitive(False)
        self.calendar_status_label.set_label("Waiting for you to finish signing in in your browser…")
        google_calendar.connect(self.on_google_connected)

    def on_google_connected(self, refresh_token, error):
        self.connect_button.set_sensitive(True)
        if error:
            self.calendar_status_label.set_label(f"Couldn't connect: {error}")
            return
        try:
            keyring.store_google_refresh_token(refresh_token)
        except keyring.KeyringError as e:
            self.calendar_status_label.set_label(f"Couldn't save to system keyring: {e}")
            return
        self._refresh_calendar_status()
        self._refresh_calendars_list()
        self.on_google_changed()

    def on_disconnect_clicked(self, _button):
        keyring.clear_google_refresh_token()
        self._refresh_calendar_status()
        self._refresh_calendars_list()
        self.on_google_changed()

    def _refresh_calendars_list(self):
        self._clear_box(self.calendars_box)
        refresh_token = keyring.lookup_google_refresh_token()
        if not refresh_token:
            self.calendars_group.set_visible(False)
            return
        self.calendars_group.set_visible(True)
        loading_label = Gtk.Label(label="Loading calendars…", xalign=0)
        loading_label.add_css_class("dim-label")
        self.calendars_box.append(loading_label)

        def worker():
            try:
                calendars = google_calendar.list_calendars(refresh_token)
            except (OSError, ValueError, KeyError) as e:
                GLib.idle_add(self._on_calendars_error, str(e))
                return
            GLib.idle_add(self._on_calendars_ready, calendars)

        threading.Thread(target=worker, daemon=True).start()

    def _on_calendars_error(self, message):
        self._clear_box(self.calendars_box)
        error_label = Gtk.Label(label=f"Couldn't load calendars: {message}", xalign=0, wrap=True)
        error_label.add_css_class("dim-label")
        self.calendars_box.append(error_label)
        return False

    def _on_calendars_ready(self, calendars):
        self._clear_box(self.calendars_box)
        selected_ids = set(self.config.get("calendar_ids") or ["primary"])
        for calendar in calendars:
            check = Gtk.CheckButton(label=calendar["summary"], active=calendar["id"] in selected_ids)
            check.connect("toggled", self._on_calendar_toggled, calendar["id"])
            self.calendars_box.append(check)
        return False

    def _on_calendar_toggled(self, check_button, calendar_id):
        selected = set(self.config.get("calendar_ids") or ["primary"])
        if check_button.get_active():
            selected.add(calendar_id)
        else:
            selected.discard(calendar_id)
        self.config["calendar_ids"] = sorted(selected)
        self.save_config(self.config)
        self.on_google_changed()

    @staticmethod
    def _clear_box(box):
        child = box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            box.remove(child)
            child = next_child

    def _refresh_updates_status(self):
        self.updates_status_label.set_label("Checking…")
        self.updates_enable_button.set_sensitive(False)
        self.updates_disable_button.set_sensitive(False)
        system_updates.get_status(self._on_updates_status_checked)

    def _on_updates_status_checked(self, status):
        installed = status["installed"]
        if not installed:
            self.updates_status_label.set_label("Not set up yet. “Run Now” in the main window works either way.")
        elif status["last_trigger"] is None:
            # Enabled, but the timer has never actually fired yet — normal
            # right after clicking Enable if 04:00 hasn't come around (or
            # gone by, via the Persistent catch-up) since.
            next_text = f" Next run: {status['next_trigger']}." if status["next_trigger"] else ""
            self.updates_status_label.set_label(f"Enabled — hasn't run yet.{next_text}")
        elif status["last_result"] == "success":
            self.updates_status_label.set_label(f"Enabled — last ran {status['last_trigger']}, succeeded.")
        else:
            self.updates_status_label.set_label(
                f"Enabled — last ran {status['last_trigger']}, but it "
                f"failed ({status['last_result'] or 'unknown result'}). "
                "See /var/log/zarya-system-update.log for details — that's a "
                "plain file anyone can read, unlike journalctl, which needs "
                "the systemd-journal group for a root-owned unit's output."
            )
        # Enable stays clickable even when already installed — it's what
        # re-syncs the on-disk unit files with whatever Zarya currently
        # bundles, e.g. after an app update ships a fixed unit file. Without
        # this, picking up such a fix would need a Disable-then-Enable dance
        # with no indication that was necessary.
        self.updates_enable_button.set_sensitive(True)
        self.updates_enable_button.set_label("Reinstall" if installed else "Enable")
        self.updates_disable_button.set_sensitive(installed)

    def on_updates_enable_clicked(self, _button):
        self.updates_enable_button.set_sensitive(False)
        self.updates_status_label.set_label("Setting up… enter your password when prompted.")
        system_updates.enable(self._on_updates_enable_done)

    def _on_updates_enable_done(self, success, error):
        if not success:
            self.updates_status_label.set_label(f"Couldn't set up: {error}")
            self.updates_enable_button.set_sensitive(True)
            return
        self._refresh_updates_status()

    def on_updates_disable_clicked(self, _button):
        self.updates_disable_button.set_sensitive(False)
        self.updates_status_label.set_label("Removing… enter your password when prompted.")
        system_updates.disable(self._on_updates_disable_done)

    def _on_updates_disable_done(self, success, error):
        if not success:
            self.updates_status_label.set_label(f"Couldn't remove: {error}")
            self.updates_disable_button.set_sensitive(True)
            return
        self._refresh_updates_status()

    def on_weather_save(self, _button):
        old_location = self.config.get("location", "")
        new_location = self.location_row.get_text().strip()
        self.config["location"] = new_location
        self.config["units"] = "celsius" if self.units_row.get_selected() == 0 else "fahrenheit"
        self.save_config(self.config)
        if new_location != old_location:
            self.on_weather_changed()
        else:
            # Units-only change — no need to hit the network again, the
            # window already has the raw Celsius data cached.
            self.on_units_changed()
