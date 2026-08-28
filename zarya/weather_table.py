import datetime

from gi.repository import Gtk

ROW_TITLES = ("Hour", "Temp", "Humidity", "Rain")


class WeatherTable(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC, vscrollbar_policy=Gtk.PolicyType.NEVER)
        self.set_min_content_height(112)
        self.grid = Gtk.Grid(
            column_spacing=10, row_spacing=4,
            margin_top=4, margin_bottom=4, margin_start=4, margin_end=4,
        )
        self.set_child(self.grid)

    def set_data(self, hours, temps, humidity, precip, temp_unit):
        child = self.grid.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.grid.remove(child)
            child = next_child

        row_titles = ("Hour", f"Temp (°{temp_unit})", "Humidity", "Rain")
        for row, title in enumerate(row_titles):
            label = Gtk.Label(label=title, xalign=1)
            label.add_css_class("dim-label")
            label.add_css_class("caption")
            self.grid.attach(label, 0, row, 1, 1)

        now_hour = datetime.datetime.now().hour

        for i, hour_iso in enumerate(hours):
            col = i + 1
            is_now = self._hour_of(hour_iso) == now_hour

            hour_label = Gtk.Label(label=self._format_hour(hour_iso))
            temp_label = Gtk.Label(label=f"{round(temps[i])}°")
            humidity_label = Gtk.Label(label=f"{round(humidity[i])}%")
            precip_label = Gtk.Label(label=f"{round(precip[i])}%")

            for label in (hour_label, temp_label, humidity_label, precip_label):
                label.set_width_chars(4)
                if is_now:
                    label.add_css_class("accent")
                    label.add_css_class("heading")

            self.grid.attach(hour_label, col, 0, 1, 1)
            self.grid.attach(temp_label, col, 1, 1, 1)
            self.grid.attach(humidity_label, col, 2, 1, 1)
            self.grid.attach(precip_label, col, 3, 1, 1)

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
        suffix = "a" if hh < 12 else "p"
        h12 = hh % 12 or 12
        return f"{h12}{suffix}"
