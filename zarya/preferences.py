import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk

from . import keyring


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
        self.units_row.set_model(Gtk.StringList.new(["Fahrenheit", "Celsius"]))
        self.units_row.set_selected(0 if config.get("units", "fahrenheit") == "fahrenheit" else 1)
        weather_group.add(self.units_row)

        weather_save_button = Gtk.Button(label="Save", halign=Gtk.Align.END)
        weather_save_button.add_css_class("suggested-action")
        weather_save_button.connect("clicked", self.on_weather_save)
        weather_group.add(weather_save_button)

        weather_page.add(weather_group)
        self.add(weather_page)

        calendar_page = Adw.PreferencesPage(title="Calendar", icon_name="x-office-calendar-symbolic")
        calendar_group = Adw.PreferencesGroup(
            title="CalDAV",
            description="Reads today's events directly from a CalDAV server, e.g. Disroot's cloud.disroot.org.",
        )

        self.server_row = Adw.EntryRow(title="Server")
        self.server_row.set_text(config.get("caldav_server", "cloud.disroot.org"))
        calendar_group.add(self.server_row)

        self.username_row = Adw.EntryRow(title="Username")
        self.username_row.set_text(config.get("caldav_username", ""))
        calendar_group.add(self.username_row)

        self.password_row = Adw.PasswordEntryRow(title="App Password")
        server = config.get("caldav_server")
        username = config.get("caldav_username")
        if server and username:
            existing = keyring.lookup_password(server, username)
            if existing:
                self.password_row.set_text(existing)
        calendar_group.add(self.password_row)

        self.calendar_status_label = Gtk.Label(xalign=0, wrap=True)
        calendar_group.add(self.calendar_status_label)

        calendar_save_button = Gtk.Button(label="Save", halign=Gtk.Align.END)
        calendar_save_button.add_css_class("suggested-action")
        calendar_save_button.connect("clicked", self.on_calendar_save)
        calendar_group.add(calendar_save_button)

        calendar_page.add(calendar_group)
        self.add(calendar_page)

    def on_weather_save(self, _button):
        self.config["location"] = self.location_row.get_text().strip()
        self.config["units"] = "fahrenheit" if self.units_row.get_selected() == 0 else "celsius"
        self.save_config(self.config)
        self.on_weather_changed()

    def on_calendar_save(self, _button):
        server = self.server_row.get_text().strip()
        username = self.username_row.get_text().strip()
        password = self.password_row.get_text()
        self.config["caldav_server"] = server
        self.config["caldav_username"] = username
        self.save_config(self.config)
        if password:
            try:
                keyring.store_password(server, username, password)
            except GLib.Error as e:
                self.calendar_status_label.set_label(f"Couldn't save password: {e}")
                return
        self.calendar_status_label.set_label("Saved.")
        self.on_calendar_changed()
