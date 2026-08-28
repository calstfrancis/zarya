from gi.repository import Gtk

HOUR_TICK_STEP = 3

# One hue per panel; each panel is a single series with its own axis, so this
# isn't a categorical set that needs CVD-pair separation — just three visually
# distinct, moderate-saturation colors that read clearly on light and dark.
TEMP_COLOR = (0.90, 0.45, 0.20)
HUMIDITY_COLOR = (0.25, 0.55, 0.85)
PRECIP_COLOR = (0.30, 0.65, 0.60)


class WeatherChart(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_content_height(230)
        self.set_hexpand(True)
        self.hours = []
        self.temps = []
        self.humidity = []
        self.precip = []
        self.temp_unit = "F"
        self.hover_index = None

        self.set_draw_func(self._draw)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

    def set_data(self, hours, temps, humidity, precip, temp_unit):
        self.hours = hours
        self.temps = temps
        self.humidity = humidity
        self.precip = precip
        self.temp_unit = temp_unit
        self.hover_index = None
        self.queue_draw()

    def _on_motion(self, _controller, x, _y):
        n = len(self.hours)
        width = self.get_width()
        if n == 0 or width <= 0:
            return
        idx = max(0, min(n - 1, int(x / width * n)))
        if idx != self.hover_index:
            self.hover_index = idx
            self.queue_draw()

    def _on_leave(self, _controller):
        self.hover_index = None
        self.queue_draw()

    def _fg_rgb(self):
        color = self.get_color()
        return (color.red, color.green, color.blue)

    def _draw(self, _area, cr, width, height, *_args):
        if not self.hours:
            return

        n = len(self.hours)
        fg = self._fg_rgb()
        x_step = width / n

        readout_h = 16
        label_h = 16
        panel_gap = 10
        panels_top = readout_h
        panels_bottom = height - label_h
        panel_h = (panels_bottom - panels_top - panel_gap * 2) / 3

        panels = [
            ("Temperature", self.temps, f"°{self.temp_unit}", TEMP_COLOR, False),
            ("Humidity", self.humidity, "%", HUMIDITY_COLOR, False),
            ("Precipitation", self.precip, "%", PRECIP_COLOR, True),
        ]

        for i, (title, series, unit, color, is_bar) in enumerate(panels):
            top = panels_top + i * (panel_h + panel_gap)
            self._draw_panel(cr, top, panel_h, width, title, series, unit, color, fg, x_step, n, is_bar)

        cr.set_source_rgba(fg[0], fg[1], fg[2], 0.6)
        cr.set_font_size(10)
        for i in range(0, n, HOUR_TICK_STEP):
            x = i * x_step
            cr.move_to(x + 2, height - 4)
            cr.show_text(self._format_hour(self.hours[i]))

        if self.hover_index is not None:
            idx = self.hover_index
            x = idx * x_step + x_step / 2
            cr.save()
            cr.set_source_rgba(fg[0], fg[1], fg[2], 0.3)
            cr.set_line_width(1)
            cr.move_to(x, panels_top)
            cr.line_to(x, panels_bottom)
            cr.stroke()
            cr.restore()

            readout = (
                f"{self._format_hour(self.hours[idx], full=True)}   "
                f"{round(self.temps[idx])}°{self.temp_unit}   "
                f"{round(self.humidity[idx])}% humidity   "
                f"{round(self.precip[idx])}% rain"
            )
            cr.set_source_rgba(fg[0], fg[1], fg[2], 0.9)
            cr.set_font_size(11)
            cr.move_to(2, 11)
            cr.show_text(readout)

    def _draw_panel(self, cr, top, h, width, title, series, unit, color, fg, x_step, n, is_bar):
        if not series:
            return
        lo = min(series)
        hi = max(series)
        if is_bar:
            lo = 0
            hi = max(hi, 10)
        elif hi == lo:
            hi = lo + 1

        plot_top = top + 12
        plot_h = h - 12

        def y_for(v):
            frac = (v - lo) / (hi - lo)
            return plot_top + plot_h - frac * plot_h

        cr.set_source_rgba(fg[0], fg[1], fg[2], 0.65)
        cr.set_font_size(10)
        cr.move_to(2, top + 9)
        cr.show_text(f"{title} ({round(lo)}–{round(hi)}{unit})")

        cr.set_source_rgba(fg[0], fg[1], fg[2], 0.12)
        cr.set_line_width(1)
        cr.move_to(0, plot_top + plot_h)
        cr.line_to(width, plot_top + plot_h)
        cr.stroke()

        if is_bar:
            bar_w = x_step * 0.6
            cr.set_source_rgba(color[0], color[1], color[2], 0.75)
            for i, v in enumerate(series):
                x = i * x_step + (x_step - bar_w) / 2
                y = y_for(v)
                cr.rectangle(x, y, bar_w, plot_top + plot_h - y)
                cr.fill()
        else:
            cr.set_source_rgba(color[0], color[1], color[2], 0.95)
            cr.set_line_width(2)
            for i, v in enumerate(series):
                x = i * x_step + x_step / 2
                y = y_for(v)
                cr.move_to(x, y) if i == 0 else cr.line_to(x, y)
            cr.stroke()

    @staticmethod
    def _format_hour(iso_str, full=False):
        try:
            hh = int(iso_str.split("T")[1].split(":")[0])
        except (IndexError, ValueError):
            return iso_str
        suffix = "am" if hh < 12 else "pm"
        h12 = hh % 12 or 12
        return f"{h12}{suffix}" if full else f"{h12}{suffix[0]}"
