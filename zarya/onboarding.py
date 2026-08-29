import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk

from . import google_calendar, keyring

PAGES = ("welcome", "location", "calendar", "done")


class OnboardingWindow(Adw.Window):
    def __init__(self, parent, config, save_config, on_finished):
        super().__init__(
            transient_for=parent, modal=True,
            default_width=460, default_height=380,
            title="Welcome to Zarya",
        )
        self.config = config
        self.save_config = save_config
        self.on_finished = on_finished
        self.page_index = 0
        self._finished = False
        self.connect("close-request", self._on_close_request)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar(show_end_title_buttons=False, show_start_title_buttons=False)
        toolbar_view.add_top_bar(header)

        self.stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
            vexpand=True,
        )
        self.stack.add_named(self._build_welcome_page(), "welcome")
        self.stack.add_named(self._build_location_page(), "location")
        self.stack.add_named(self._build_calendar_page(), "calendar")
        self.stack.add_named(self._build_done_page(), "done")
        toolbar_view.set_content(self.stack)

        bottom_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
            margin_top=6, margin_bottom=12, margin_start=12, margin_end=12,
        )
        self.back_button = Gtk.Button(label="Back")
        self.back_button.connect("clicked", lambda *_: self._go(-1))
        bottom_bar.append(self.back_button)
        bottom_bar.append(Gtk.Box(hexpand=True))
        self.next_button = Gtk.Button(label="Get Started")
        self.next_button.add_css_class("suggested-action")
        self.next_button.connect("clicked", self.on_next_clicked)
        bottom_bar.append(self.next_button)
        toolbar_view.add_bottom_bar(bottom_bar)

        self.set_content(toolbar_view)
        self._update_nav()

    def _build_welcome_page(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER,
            margin_top=24, margin_bottom=24, margin_start=24, margin_end=24,
        )
        title = Gtk.Label(label="Welcome to Zarya")
        title.add_css_class("title-1")
        box.append(title)
        subtitle = Gtk.Label(
            label="A couple of quick things to set up — your city for the weather report, "
                  "and your Google Account if you'd like today's events and a synced "
                  "to-do list on the dashboard. Both are optional and can be changed "
                  "later in Preferences.",
            wrap=True, justify=Gtk.Justification.CENTER,
        )
        subtitle.add_css_class("dim-label")
        box.append(subtitle)
        return box

    def _build_location_page(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER,
            margin_top=24, margin_bottom=24, margin_start=24, margin_end=24,
        )
        title = Gtk.Label(label="Your city")
        title.add_css_class("title-2")
        box.append(title)
        subtitle = Gtk.Label(
            label="Used for the daily weather report (temperatures shown in °C by default — "
                  "change that anytime in Preferences).",
            wrap=True, justify=Gtk.Justification.CENTER,
        )
        subtitle.add_css_class("dim-label")
        box.append(subtitle)
        self.location_entry = Gtk.Entry(placeholder_text="City, Country")
        if self.config.get("location"):
            self.location_entry.set_text(self.config["location"])
        box.append(self.location_entry)
        return box

    def _build_calendar_page(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER,
            margin_top=24, margin_bottom=24, margin_start=24, margin_end=24,
        )
        title = Gtk.Label(label="Google Account")
        title.add_css_class("title-2")
        box.append(title)
        subtitle = Gtk.Label(
            label="Connect it to see today's Calendar events and sync the to-do sidebar "
                  "with Google Tasks. Only a refresh token is stored, in your system keyring.",
            wrap=True, justify=Gtk.Justification.CENTER,
        )
        subtitle.add_css_class("dim-label")
        box.append(subtitle)
        self.connect_button = Gtk.Button(label="Connect Google Account", halign=Gtk.Align.CENTER)
        self.connect_button.add_css_class("pill")
        self.connect_button.connect("clicked", self.on_connect_clicked)
        box.append(self.connect_button)
        self.calendar_status_label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.calendar_status_label.add_css_class("dim-label")
        box.append(self.calendar_status_label)
        return box

    def _build_done_page(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER,
            margin_top=24, margin_bottom=24, margin_start=24, margin_end=24,
        )
        title = Gtk.Label(label="You're all set")
        title.add_css_class("title-1")
        box.append(title)
        subtitle = Gtk.Label(
            label="Zarya will run your system update now. Everything here can be changed "
                  "later from the Preferences menu.",
            wrap=True, justify=Gtk.Justification.CENTER,
        )
        subtitle.add_css_class("dim-label")
        box.append(subtitle)
        return box

    def _update_nav(self):
        page = PAGES[self.page_index]
        self.back_button.set_visible(self.page_index > 0)
        if page == "welcome":
            self.next_button.set_label("Get Started")
        elif page == "location":
            self.next_button.set_label("Next")
        elif page == "calendar":
            connected = bool(keyring.lookup_google_refresh_token())
            self.next_button.set_label("Continue" if connected else "Skip for now")
        else:
            self.next_button.set_label("Finish")

    def _go(self, delta):
        self.page_index = max(0, min(len(PAGES) - 1, self.page_index + delta))
        self.stack.set_visible_child_name(PAGES[self.page_index])
        self._update_nav()

    def on_next_clicked(self, _button):
        page = PAGES[self.page_index]
        if page == "location":
            self.config["location"] = self.location_entry.get_text().strip()
            self.config.setdefault("units", "celsius")
            self.save_config(self.config)
        if page == "done":
            self._finish()
            self.close()
            return
        self._go(1)

    def on_connect_clicked(self, _button):
        self.connect_button.set_sensitive(False)
        self.calendar_status_label.set_label("Waiting for you to finish signing in in your browser…")
        google_calendar.connect(self.on_google_connected)

    def on_google_connected(self, refresh_token, error):
        self.connect_button.set_sensitive(True)
        if error:
            self.calendar_status_label.set_label(f"Couldn't connect: {error}")
            return
        keyring.store_google_refresh_token(refresh_token)
        self.calendar_status_label.set_label("Connected.")
        self._update_nav()

    def _on_close_request(self, _window):
        self._finish()
        return False

    def _finish(self):
        if self._finished:
            return
        self._finished = True
        self.config["onboarded"] = True
        self.save_config(self.config)
        self.on_finished()
