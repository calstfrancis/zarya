import threading

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk

from . import google_calendar, keyring


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

        self._refresh_calendar_status()
        self._refresh_calendars_list()

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
