import datetime

from gi.repository import GLib, Gtk


class WeatherTable(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._hours = []

        self.label_grid = Gtk.Grid(
            column_spacing=10, row_spacing=4,
            margin_top=4, margin_bottom=4, margin_start=4, margin_end=8,
        )
        for row, title in enumerate(("Hour", "Temp", "Rain", "Humidity")):
            label = Gtk.Label(label=title, xalign=1)
            label.add_css_class("dim-label")
            label.add_css_class("caption")
            self.label_grid.attach(label, 0, row, 1, 1)
        self.append(self.label_grid)

        self.data_grid = Gtk.Grid(
            column_spacing=10, row_spacing=4,
            margin_top=4, margin_bottom=4, margin_start=0, margin_end=4,
        )
        self.data_grid.add_css_class("weather-figures")
        self.scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.NEVER,
            hexpand=True,
        )
        self.scroller.set_min_content_height(112)
        self.scroller.set_child(self.data_grid)
        self.append(self.scroller)

        # Plain wheel scroll defaults to vertical, which does nothing here
        # since there's no vertical overflow — redirect it to horizontal.
        scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll_controller.connect("scroll", self._on_scroll)
        self.scroller.add_controller(scroll_controller)

    def _on_scroll(self, _controller, dx, dy):
        adj = self.scroller.get_hadjustment()
        delta = dx if dx else dy
        adj.set_value(max(adj.get_lower(), min(adj.get_upper() - adj.get_page_size(), adj.get_value() + delta * 40)))
        return True

    def set_data(self, hours, temps, humidity, precip, temp_unit):
        self._hours = hours

        child = self.label_grid.get_child_at(0, 1)
        if child is not None:
            child.set_label(f"Temp (°{temp_unit})")

        # No rain in the forecast window at all — hide the whole Rain row
        # rather than a column of 25 "0%" labels nobody needs to read.
        has_rain = any(round(p) > 0 for p in precip)
        rain_row_label = self.label_grid.get_child_at(0, 2)
        if rain_row_label is not None:
            rain_row_label.set_visible(has_rain)

        child = self.data_grid.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.data_grid.remove(child)
            child = next_child

        now_hour = datetime.datetime.now().hour

        for i, hour_iso in enumerate(hours):
            is_now = self._hour_of(hour_iso) == now_hour

            hour_text = "Now" if is_now else self._format_hour(hour_iso)
            hour_label = Gtk.Label(label=hour_text)
            temp_label = Gtk.Label(label=f"{round(temps[i])}°")
            humidity_label = Gtk.Label(label=f"{round(humidity[i])}%")

            for label in (hour_label, temp_label, humidity_label):
                label.set_width_chars(6)
                if is_now:
                    label.add_css_class("now-hour")

            self.data_grid.attach(hour_label, i, 0, 1, 1)
            self.data_grid.attach(temp_label, i, 1, 1, 1)
            self.data_grid.attach(humidity_label, i, 3, 1, 1)

            if has_rain:
                precip_label = Gtk.Label(label=f"{round(precip[i])}%")
                precip_label.set_width_chars(6)
                if is_now:
                    precip_label.add_css_class("now-hour")
                self.data_grid.attach(precip_label, i, 2, 1, 1)

    def center_on_now(self):
        now_hour = datetime.datetime.now().hour
        idx = None
        for i, hour_iso in enumerate(self._hours):
            if self._hour_of(hour_iso) == now_hour:
                idx = i
                break
        if idx is None:
            return

        # Polling get_width() until it's nonzero used to give up after 20
        # attempts (~600ms), which wasn't always enough for the table to be
        # realized and allocated on first launch — the real, user-visible
        # bug this was fixed for: the hourly strip silently stayed scrolled
        # to its leftmost (oldest) hours instead of centering on "now".
        # ~3s of polling at a light interval costs nothing once the width
        # does resolve (it stops immediately), and is a much safer margin.
        attempts = [0]

        def attempt():
            width = self.data_grid.get_width()
            if width <= 0:
                attempts[0] += 1
                return attempts[0] < 100
            n = max(1, len(self._hours))
            col_width = width / n
            adj = self.scroller.get_hadjustment()
            target = col_width * idx + col_width / 2 - adj.get_page_size() / 2
            adj.set_value(max(adj.get_lower(), min(adj.get_upper() - adj.get_page_size(), target)))
            return False

        GLib.timeout_add(30, attempt)

    @staticmethod
    def _hour_of(iso_str):
        try:
            return int(iso_str.split("T")[1].split(":")[0])
        except (IndexError, ValueError):
            return None

    @classmethod
    def _format_hour(cls, iso_str):
        hh = cls._hour_of(iso_str)
        if hh is None:
            return iso_str
        suffix = "AM" if hh < 12 else "PM"
        h12 = hh % 12 or 12
        return f"{h12} {suffix}"
