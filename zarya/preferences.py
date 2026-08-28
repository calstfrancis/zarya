import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk

from . import google_calendar, keyring


class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, parent, config, save_config, on_weather_changed, on_calendar_changed):
        super().__init__(transient_for=parent, modal=True)
        self.config = config
        self.save_config = save_config
        self.on_weather_changed = on_weather_changed
        self.on_calendar_changed = on_calendar_changed

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

        calendar_page = Adw.PreferencesPage(title="Calendar", icon_name="x-office-calendar-symbolic")
        calendar_group = Adw.PreferencesGroup(
            title="Google Calendar",
            description="Opens your browser to sign in; only a read-only refresh token is stored, in the system keyring.",
        )

        self.calendar_status_label = Gtk.Label(xalign=0, wrap=True)
        calendar_group.add(self.calendar_status_label)

        calendar_button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        self.connect_button = Gtk.Button(label="Connect Google Calendar")
        self.connect_button.add_css_class("suggested-action")
        self.connect_button.connect("clicked", self.on_connect_clicked)
        calendar_button_row.append(self.connect_button)

        self.disconnect_button = Gtk.Button(label="Disconnect")
        self.disconnect_button.connect("clicked", self.on_disconnect_clicked)
        calendar_button_row.append(self.disconnect_button)

        calendar_group.add(calendar_button_row)

        calendar_page.add(calendar_group)
        self.add(calendar_page)

        self._refresh_calendar_status()

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
        self.on_calendar_changed()

    def on_disconnect_clicked(self, _button):
        keyring.clear_google_refresh_token()
        self._refresh_calendar_status()
        self.on_calendar_changed()

    def on_weather_save(self, _button):
        self.config["location"] = self.location_row.get_text().strip()
        self.config["units"] = "celsius" if self.units_row.get_selected() == 0 else "fahrenheit"
        self.save_config(self.config)
        self.on_weather_changed()
