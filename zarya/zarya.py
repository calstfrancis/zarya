import datetime
import json
import re
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from . import __version__, backup_status, changelog, disk_growth, google_calendar, habits, keyring, styles, system_health, system_updates, tray, weather, weather_alerts, weather_aqi
from .onboarding import OnboardingWindow
from .preferences import PreferencesWindow
from .todo_sidebar import TodoSidebar
from .weather_table import WeatherTable

APP_ID = "io.github.calstfrancis.zarya"

# --background: launched from the autostart entry, not by the user directly —
# stay hidden in the tray and only run the update/fetches, rather than
# popping a window open at every login. A manual `flatpak run` (no flag)
# still opens the window immediately, same as always.
AUTOSTART_CONTENT = f"""[Desktop Entry]
Type=Application
Name=Zarya
Comment=Runs system and flatpak updates at login
Exec=flatpak run {APP_ID} --background
Icon={APP_ID}
X-Flatpak={APP_ID}
NoDisplay=true
"""


def marker_path() -> Path:
    return Path(GLib.get_user_cache_dir()) / "zarya" / "lastrun"


def timer_failure_marker_path() -> Path:
    # Separate from marker_path()/mark_done(): records that today's *timer*
    # failure has already been reported into history/notifications once,
    # without marking the day itself "done" — a failed automatic run should
    # still leave "Run Now" available (not flip to "Run Anyway"), since
    # nothing actually succeeded yet.
    return Path(GLib.get_user_cache_dir()) / "zarya" / "lasttimerfailure"


def result_path() -> Path:
    return Path(GLib.get_user_cache_dir()) / "zarya" / "lastresult.json"


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


def load_result():
    path = result_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_result(success: bool) -> None:
    now = datetime.datetime.now()
    path = result_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "date": now.date().isoformat(),
        "success": success,
        "time": now.strftime("%H:%M"),
    }))


def history_path() -> Path:
    return Path(GLib.get_user_cache_dir()) / "zarya" / "history.json"


HISTORY_LIMIT = 14


def load_history() -> list:
    path = history_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []


def append_history(success: bool) -> list:
    history = load_history()
    history.append({"date": datetime.date.today().isoformat(), "success": success})
    history = history[-HISTORY_LIMIT:]
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history))
    return history


def summarize_updates(text):
    """Best-effort summary of what actually changed, parsed from zypper's and
    flatpak's own output — never load-bearing, just a nicety, so any failure
    to match just means no summary line rather than a crash."""
    parts = []
    m = re.search(
        r"(\d+) packages? to upgrade(?:,\s*(\d+) new)?(?:,\s*(\d+) to (?:remove|downgrade))?",
        text,
    )
    if m:
        upgrade, new, remove = m.groups()
        bits = [f"{upgrade} upgraded"]
        if new:
            bits.append(f"{new} new")
        if remove:
            bits.append(f"{remove} removed")
        parts.append("zypper: " + ", ".join(bits))
    flatpak_count = len(re.findall(r"^\s*\d+\.\s+\S+", text, re.M))
    if flatpak_count:
        parts.append(f"flatpak: {flatpak_count} updated")
    return " · ".join(parts) if parts else None


def _check_unit_already_ran_today(callback):
    """Async: callback(ran_today, succeeded_today, failed_today) for the
    passwordless-update timer's last completed run (see system_updates.py's
    SYSTEM_UPDATE_* constants and "Passwordless daily updates" in
    zarya/CLAUDE.md) — a thin wrapper around system_updates.get_status(),
    the single source of truth for reading this unit's state (also used by
    Preferences > Updates' own status display). Zarya only ever *reads*
    this — the root-owned timer runs the actual update on its own schedule,
    with no password prompt and no involvement from Zarya at all; "Run Now"
    still goes through the original pkexec prompt unchanged, since that's a
    deliberate manual action, not the unattended case this exists to fix."""
    system_updates.get_status(
        lambda status: callback(status["ran_today"], status["succeeded_today"], status["failed_today"])
    )


STATE_COLORS = {
    "ok": "success",
    "failed": "error",
    "running": "accent",
    "paused": "dim-label",
    "idle": "dim-label",
    "skipped": "dim-label",
}

STATE_LABELS = {
    "ok": "OK",
    "failed": "Failed",
    "running": "Running",
    "paused": "Paused",
    "idle": "Idle",
    "skipped": "Skipped",
}

# Status is never color-alone anywhere in Zarya (matches the accessibility
# commitments on calstfrancis.github.io) — every colored state label pairs
# with one of these icons too.
STATE_ICONS = {
    "ok": "emblem-ok-symbolic",
    "failed": "dialog-error-symbolic",
    "running": "content-loading-symbolic",
    "paused": "media-playback-pause-symbolic",
    "idle": "media-playback-stop-symbolic",
    "skipped": "action-unavailable-symbolic",
}


def _wire_hover_reveal(row, *widgets):
    """Fades `widgets` (typically a delete/remove button) in only while the
    pointer is over `row` — CSS `:hover` doesn't reliably bubble from a
    plain container to its children in GTK4, so this drives it directly
    off pointer enter/leave instead. Same helper as todo_sidebar.py's."""
    controller = Gtk.EventControllerMotion()
    controller.connect("enter", lambda *_a: [w.set_opacity(1) for w in widgets])
    controller.connect("leave", lambda *_a: [w.set_opacity(0) for w in widgets])
    row.add_controller(controller)


class ZaryaWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Zarya")
        self.set_default_size(980, 780)

        self.proc = None
        self._phase = None
        self._interactive = True
        self.weather_data = None
        self.config = load_config()
        self.quitting = False
        self.tray = tray.TrayIcon(APP_ID, self.on_tray_activate)
        self.connect("close-request", self.on_close_request)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title="Zarya")
        header.set_title_widget(self.window_title)
        toolbar_view.add_top_bar(header)

        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self.menu_popover = Gtk.Popover()
        menu_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=2,
            margin_top=6, margin_bottom=6, margin_start=6, margin_end=6,
        )
        prefs_button = Gtk.Button(label="Preferences", has_frame=False)
        prefs_button.set_halign(Gtk.Align.FILL)
        prefs_button.get_child().set_halign(Gtk.Align.START)
        prefs_button.connect("clicked", self.on_preferences_clicked)
        menu_box.append(prefs_button)
        whats_new_button = Gtk.Button(label="What's New", has_frame=False)
        whats_new_button.set_halign(Gtk.Align.FILL)
        whats_new_button.get_child().set_halign(Gtk.Align.START)
        whats_new_button.connect("clicked", self.on_whats_new_clicked)
        menu_box.append(whats_new_button)
        about_button = Gtk.Button(label="About Zarya", has_frame=False)
        about_button.set_halign(Gtk.Align.FILL)
        about_button.get_child().set_halign(Gtk.Align.START)
        about_button.connect("clicked", self.on_about_clicked)
        menu_box.append(about_button)
        quit_button = Gtk.Button(label="Quit Zarya", has_frame=False)
        quit_button.set_halign(Gtk.Align.FILL)
        quit_button.get_child().set_halign(Gtk.Align.START)
        quit_button.connect("clicked", self.on_quit_clicked)
        menu_box.append(quit_button)
        self.menu_popover.set_child(menu_box)
        menu_button.set_popover(self.menu_popover)
        header.pack_end(menu_button)

        refresh_all_button = Gtk.Button(icon_name="view-refresh-symbolic", has_frame=False)
        refresh_all_button.set_tooltip_text("Refresh everything")
        refresh_all_button.connect("clicked", self.on_refresh_all_clicked)
        header.pack_end(refresh_all_button)

        self.restart_banner = Adw.Banner(
            title="A new version of Zarya was installed — restart to start using it.",
            button_label="Restart Now",
        )
        self.restart_banner.connect("button-clicked", lambda *_: self.restart_now())
        toolbar_view.add_top_bar(self.restart_banner)

        self.toast_overlay = Adw.ToastOverlay()

        root_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        self.root_box = root_box

        # --- Weather ---
        weather_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        weather_content.add_css_class("fondwave-card")

        weather_top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.weather_summary_label = Gtk.Label(xalign=0, hexpand=True, wrap=True)
        self.weather_summary_label.set_label("Set a location in Preferences to see today's weather.")
        weather_top_row.append(self.weather_summary_label)
        self.weather_current_label = Gtk.Label(xalign=1)
        self.weather_current_label.add_css_class("title-4")
        weather_top_row.append(self.weather_current_label)
        weather_content.append(weather_top_row)

        weather_second_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.weather_sun_label = Gtk.Label(xalign=0, hexpand=True)
        self.weather_sun_label.add_css_class("caption")
        self.weather_sun_label.add_css_class("dim-label")
        weather_second_row.append(self.weather_sun_label)
        self.weather_aqi_label = Gtk.Label(xalign=1, halign=Gtk.Align.END)
        self.weather_aqi_label.add_css_class("caption")
        weather_second_row.append(self.weather_aqi_label)
        weather_content.append(weather_second_row)

        self.alerts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        weather_content.append(self.alerts_box)

        self.weather_table = WeatherTable()
        self.weather_table.set_visible(False)
        weather_content.append(self.weather_table)
        self.weather_expander, self.weather_status_icon = self._make_section(
            "weather", "Weather", weather_content
        )
        root_box.append(self.weather_expander)

        # --- Today's events ---
        self.events_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.events_expander, self.events_status_icon = self._make_section(
            "events", "Today's Events & Due Dates", self.events_box
        )
        root_box.append(self.events_expander)

        # --- Status row: System, Backups, Updates ---
        # Folded from what used to be three-to-four separate always-expanded
        # sections (System Health, Backups, Disk Growth, plus the bottom
        # button row for Updates) into three compact cards. A card only
        # takes on color/detail text when something actually needs
        # attention — the common case (everything fine) should be quiet,
        # not a full page of "OK" rows.
        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, homogeneous=True)
        self.status_row = status_row
        root_box.append(status_row)

        # System (+ Disk Growth folded in — both are "state of the machine")
        self.health_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.disk_growth_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.system_detail_body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=10, margin_bottom=10, margin_start=12, margin_end=12)
        self.system_detail_body.set_size_request(320, -1)
        self.system_detail_body.append(self._popover_heading("Storage & Drives", self.fetch_system_health))
        self.system_detail_body.append(self.health_box)
        self.system_detail_body.append(Gtk.Separator())
        self.system_detail_body.append(self._popover_heading("Growing This Week", self.fetch_disk_growth))
        self.system_detail_body.append(self.disk_growth_box)
        self.system_card, self.system_card_value, self.system_card_detail = self._make_status_card(
            "computer-symbolic", "System", self.system_detail_body,
        )
        self.system_card_value.set_label("Checking…")
        status_row.append(self.system_card)

        # Backups
        self.backup_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.backups_detail_body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=10, margin_bottom=10, margin_start=12, margin_end=12)
        self.backups_detail_body.set_size_request(320, -1)
        self.backups_detail_body.append(self._popover_heading("Backups", self.fetch_backups))
        self.backups_detail_body.append(self.backup_box)
        open_pereprava_button = Gtk.Button(label="Open Pereprava", halign=Gtk.Align.START)
        open_pereprava_button.connect("clicked", self.on_open_pereprava_clicked)
        self.backups_detail_body.append(open_pereprava_button)
        self.backups_card, self.backups_card_value, self.backups_card_detail = self._make_status_card(
            "folder-remote-symbolic", "Backups", self.backups_detail_body,
        )
        self.backups_card_value.set_label("Checking…")
        status_row.append(self.backups_card)

        # Updates — the old bottom button row and its Update Log now live
        # entirely inside this card's popover (or inline, in the wide
        # layout — see _on_wide_layout).
        self.updates_detail_body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=10, margin_bottom=10, margin_start=12, margin_end=12)
        self.updates_detail_body.set_size_request(360, -1)

        self.status_label = Gtk.Label(xalign=0)
        self.status_label.add_css_class("heading")
        self.updates_detail_body.append(self.status_label)

        result_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.result_icon = Gtk.Image()
        self.result_label = Gtk.Label(xalign=0, wrap=True)
        result_box.append(self.result_icon)
        result_box.append(self.result_label)
        self.updates_detail_body.append(result_box)

        self.history_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        history_caption = Gtk.Label(label="Last 14 days:")
        history_caption.add_css_class("dim-label")
        history_caption.add_css_class("caption")
        self.history_row.append(history_caption)
        self.history_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.history_row.append(self.history_box)
        self.updates_detail_body.append(self.history_row)

        updates_button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.run_button = Gtk.Button(label="Run Now")
        self.run_button.add_css_class("suggested-action")
        self.run_button.connect("clicked", self.on_run_clicked)
        updates_button_row.append(self.run_button)
        self.cancel_button = Gtk.Button(label="Cancel")
        self.cancel_button.set_sensitive(False)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)
        updates_button_row.append(self.cancel_button)
        self.updates_detail_body.append(updates_button_row)

        log_expander = Gtk.Expander(label="Update Log")
        log_expander.set_expanded(self.config.get("log_expanded", False))
        log_expander.connect("notify::expanded", self._on_section_toggled, "log")
        scrolled = Gtk.ScrolledWindow(vexpand=False)
        scrolled.set_min_content_height(220)
        scrolled.set_size_request(-1, 220)
        scrolled.add_css_class("card")
        scrolled.add_css_class("fondwave-terminal")
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
        self.log_error_tag = self.buffer.create_tag("log-error", foreground=styles.TERMINAL_RED)
        self.log_success_tag = self.buffer.create_tag("log-success", foreground=styles.TERMINAL_GREEN)
        scrolled.set_child(self.text_view)
        log_expander.set_child(scrolled)
        self.updates_detail_body.append(log_expander)

        self.updates_card, self.updates_card_value, self.updates_card_detail = self._make_status_card(
            "software-update-available-symbolic", "Updates", self.updates_detail_body,
        )
        status_row.append(self.updates_card)

        # --- Wide layout (maximized-ish widths): Today's Events beside the
        # status cards shown in FULL (their detail body inline, not behind
        # a click-through popover) — see _on_wide_layout for how the same
        # detail-body widgets move between a popover and here.
        self.system_wide_card = self._make_wide_card("computer-symbolic", "System")
        self.backups_wide_card = self._make_wide_card("folder-remote-symbolic", "Backups")
        self.updates_wide_card = self._make_wide_card("software-update-available-symbolic", "Updates")
        self.wide_status_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.wide_status_column.append(self.system_wide_card)
        self.wide_status_column.append(self.backups_wide_card)
        self.wide_status_column.append(self.updates_wide_card)

        # `wide_row` isn't parented anywhere yet — the breakpoint below
        # moves `events_expander`/`wide_status_column` into it (and back
        # out again below the min-width) rather than building two separate
        # copies of that content.
        self.wide_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        wide_breakpoint = Adw.Breakpoint.new(
            Adw.BreakpointCondition.new_length(Adw.BreakpointConditionLengthType.MIN_WIDTH, 1200, Adw.LengthUnit.PX)
        )
        wide_breakpoint.connect("apply", self._on_wide_layout)
        wide_breakpoint.connect("unapply", self._on_narrow_layout)
        self.add_breakpoint(wide_breakpoint)

        # --- Habits (lives in the sidebar, below To-Do — see main_paned below) ---
        self.habits_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)

        root_scrolled = Gtk.ScrolledWindow(vexpand=True)
        root_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        root_scrolled.set_child(root_box)
        self.toast_overlay.set_child(root_scrolled)

        self.todo_sidebar = TodoSidebar()

        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, vexpand=True)
        sidebar_box.append(self.todo_sidebar)

        habits_card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6,
            margin_top=0, margin_bottom=10, margin_start=8, margin_end=12,
        )
        habits_card.add_css_class("fondwave-terminal")
        habits_card.add_css_class("card")
        habits_header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        habits_title = Gtk.Label(label="Habits", xalign=0, hexpand=True)
        habits_title.add_css_class("title-4")
        habits_header_row.append(habits_title)
        add_habit_button = Gtk.Button(icon_name="list-add-symbolic", has_frame=False)
        add_habit_button.set_tooltip_text("Add a habit")
        add_habit_button.connect("clicked", self.on_add_habit_clicked)
        habits_header_row.append(add_habit_button)
        habits_card.append(habits_header_row)
        habits_card.append(self.habits_box)
        sidebar_box.append(habits_card)

        main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        main_paned.set_start_child(self.toast_overlay)
        main_paned.set_resize_start_child(True)
        main_paned.set_shrink_start_child(False)
        main_paned.set_end_child(sidebar_box)
        main_paned.set_resize_end_child(False)
        main_paned.set_shrink_end_child(False)
        main_paned.set_position(self.config.get("sidebar_paned_position", 700))
        self._paned_ready = False
        GLib.timeout_add(500, self._on_paned_ready)
        main_paned.connect("notify::position", self._on_paned_position_changed)
        self._paned_save_timeout = None
        self._heal_stale_autostart_entry()

        toolbar_view.set_content(main_paned)
        self.set_content(toolbar_view)

        self.refresh_status()
        if self.config.get("location"):
            self.fetch_weather()
        GLib.timeout_add_seconds(3600, self._on_weather_refresh_timer)
        GLib.timeout_add_seconds(600, self._on_gradient_refresh_timer)
        self.fetch_backups()
        GLib.timeout_add_seconds(600, self._on_backups_refresh_timer)
        self.fetch_system_health()
        GLib.timeout_add_seconds(300, self._on_health_refresh_timer)
        if keyring.lookup_google_refresh_token():
            self.fetch_events()
        else:
            self._set_box_message(self.events_box, "Connect your Google Account in Preferences to see today's events.")
        GLib.timeout_add_seconds(900, self._on_events_refresh_timer)
        self.fetch_disk_growth()
        GLib.timeout_add_seconds(21600, self._on_disk_growth_refresh_timer)
        self.render_habits()

        # The autostart entry only runs at an actual login — on a machine
        # that stays logged in across suspend/resume for days at a stretch
        # (this one reboots roughly weekly but suspends daily), that means
        # the very first login of the week is the *only* time the process
        # is ever (re)launched, so the daily auto-run would otherwise never
        # fire again on the days in between. Since the app stays resident in
        # the tray across those days, poll for a day rollover instead of
        # relying solely on being relaunched.
        GLib.timeout_add_seconds(300, self._maybe_autorun)
        self._update_window_title()

    def _heal_stale_autostart_entry(self):
        """Keep an already-enabled autostart entry in sync with the current
        AUTOSTART_CONTENT. Written once when the switch is toggled on, so a
        file from before a change to that template (e.g. the --background
        flag added in v0.4.0) would otherwise sit stale forever."""
        path = autostart_path()
        if not path.exists():
            return
        try:
            if path.read_text() != AUTOSTART_CONTENT:
                path.write_text(AUTOSTART_CONTENT)
        except OSError:
            pass

    def _maybe_autorun(self):
        if (
            self.proc is None
            and self.config.get("onboarded")
            and autostart_path().exists()
            and not self.already_ran_today()
        ):
            self.start_updates(interactive=False)
        return True

    def _make_section(self, key, title, content, on_refresh=None, extra_button=None, show_icon=True):
        status_icon = Gtk.Image()
        status_icon.set_pixel_size(16)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_label = Gtk.Label(label=title, xalign=0, hexpand=True)
        title_label.add_css_class("heading")
        header_box.append(title_label)
        if show_icon:
            header_box.append(status_icon)
        if extra_button is not None:
            header_box.append(extra_button)
        if on_refresh is not None:
            refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", has_frame=False)
            refresh_button.set_tooltip_text(f"Refresh {title.lower()}")
            refresh_button.connect("clicked", lambda *_: on_refresh())
            header_box.append(refresh_button)

        expander = Gtk.Expander()
        expander.set_label_widget(header_box)
        expander.set_child(content)
        expander.set_expanded(self.config.get(f"{key}_expanded", True))
        expander.connect("notify::expanded", self._on_section_toggled, key)
        return expander, status_icon

    def _on_section_toggled(self, expander, _pspec, key):
        self.config[f"{key}_expanded"] = expander.get_expanded()
        save_config(self.config)

    @staticmethod
    def _popover_heading(title, on_refresh):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label = Gtk.Label(label=title, xalign=0, hexpand=True)
        label.add_css_class("heading")
        row.append(label)
        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", has_frame=False)
        refresh_button.set_tooltip_text(f"Refresh {title.lower()}")
        refresh_button.connect("clicked", lambda *_: on_refresh())
        row.append(refresh_button)
        return row

    def _make_status_card(self, icon_name, title, popover_content):
        """A compact status card (System/Backups/Updates): a title, a
        one-line value, and an optional detail line, all on a MenuButton
        face whose popover holds the full detail — folds what used to be
        several always-expanded sections (plus the bottom button row, for
        Updates) into something that only takes space when clicked."""
        card = Gtk.MenuButton()
        card.add_css_class("status-card")
        card.add_css_class("flat")
        card.set_valign(Gtk.Align.START)
        card.set_hexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        top_row.append(Gtk.Image(icon_name=icon_name))
        title_label = Gtk.Label(label=title, xalign=0, hexpand=True)
        title_label.add_css_class("status-card-title")
        top_row.append(title_label)
        box.append(top_row)

        value_label = Gtk.Label(xalign=0, wrap=True)
        value_label.add_css_class("status-card-value")
        box.append(value_label)

        detail_label = Gtk.Label(xalign=0, wrap=True)
        detail_label.add_css_class("caption")
        detail_label.add_css_class("dim-label")
        detail_label.set_visible(False)
        box.append(detail_label)

        card.set_child(box)

        popover = Gtk.Popover()
        popover.set_child(popover_content)
        card.set_popover(popover)

        return card, value_label, detail_label

    @staticmethod
    def _make_wide_card(icon_name, title):
        """The wide-layout counterpart of a status card: a real card with
        an icon+title header, but no popover — its detail body is appended
        directly below the header (by `_on_wide_layout`, moving the same
        widget that lives in the compact card's popover in narrow mode), so
        the full detail is always visible without a click."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("status-card")
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.append(Gtk.Image(icon_name=icon_name))
        title_label = Gtk.Label(label=title, xalign=0, hexpand=True)
        title_label.add_css_class("heading")
        header.append(title_label)
        card.append(header)
        return card

    @staticmethod
    def _set_card_state(card, kind):
        """kind: "ok" (quiet, no color), "warning", or "error"."""
        card.remove_css_class("warning")
        card.remove_css_class("error")
        if kind in ("warning", "error"):
            card.add_css_class(kind)

    def _set_status_severity(self, name, kind):
        """Applies `kind` to both the compact card (narrow layout) and its
        wide-layout counterpart, so the two stay in sync regardless of
        which one is currently visible — `name` is "system"/"backups"/
        "updates", matching the `{name}_card`/`{name}_wide_card` attrs."""
        self._set_card_state(getattr(self, f"{name}_card"), kind)
        self._set_card_state(getattr(self, f"{name}_wide_card"), kind)

    # (name, detail_body attr, wide-card attr) for the three status cards —
    # walked by _on_wide_layout/_on_narrow_layout to move each card's detail
    # body between its popover (narrow layout) and its wide-card frame
    # (wide layout), so the same widgets show either behind a click or
    # always inline rather than building two copies of the content.
    _STATUS_CARD_NAMES = ("system", "backups", "updates")

    def _on_wide_layout(self, _breakpoint):
        """Window widened past the breakpoint (typically maximized): move
        Today's Events and the status cards out of the single scrolling
        column and side by side instead — Events on the left (still
        growing to fill the space), the three status cards stacked in a
        narrower column on the right with their full detail shown inline
        (no click needed), so a maximized window uses its width instead of
        just stretching a single column across it."""
        self.root_box.remove(self.events_expander)
        self.root_box.remove(self.status_row)
        self.events_expander.set_hexpand(True)

        for name in self._STATUS_CARD_NAMES:
            compact_card = getattr(self, f"{name}_card")
            wide_card = getattr(self, f"{name}_wide_card")
            detail_body = getattr(self, f"{name}_detail_body")
            compact_card.get_popover().set_child(None)
            wide_card.append(detail_body)

        self.wide_status_column.set_size_request(320, -1)
        self.wide_status_column.set_hexpand(False)
        self.wide_row.append(self.events_expander)
        self.wide_row.append(self.wide_status_column)
        self.root_box.insert_child_after(self.wide_row, self.weather_expander)

    def _on_narrow_layout(self, _breakpoint):
        """Window narrower than the breakpoint again — put Today's Events
        and the status cards back into their normal stacked, click-for-
        detail order."""
        self.root_box.remove(self.wide_row)
        self.wide_row.remove(self.events_expander)
        self.wide_row.remove(self.wide_status_column)
        self.events_expander.set_hexpand(False)

        for name in self._STATUS_CARD_NAMES:
            compact_card = getattr(self, f"{name}_card")
            wide_card = getattr(self, f"{name}_wide_card")
            detail_body = getattr(self, f"{name}_detail_body")
            wide_card.remove(detail_body)
            compact_card.get_popover().set_child(detail_body)

        self.root_box.insert_child_after(self.events_expander, self.weather_expander)
        self.root_box.insert_child_after(self.status_row, self.events_expander)

    @staticmethod
    def _set_status_icon(icon, kind):
        icon.remove_css_class("success")
        icon.remove_css_class("error")
        if kind == "ok":
            icon.set_from_icon_name("emblem-ok-symbolic")
            icon.add_css_class("success")
        elif kind == "error":
            icon.set_from_icon_name("dialog-error-symbolic")
            icon.add_css_class("error")
        else:
            icon.set_from_icon_name(None)

    # --- sidebar paned ---

    def _on_paned_ready(self):
        # Setting the initial position programmatically also fires
        # notify::position — ignore events until the window's had a moment
        # to actually lay out, so that initial pass never gets persisted
        # back into config as if the user had dragged it.
        self._paned_ready = True
        return False

    def _on_paned_position_changed(self, paned, _pspec):
        if not self._paned_ready:
            return
        if self._paned_save_timeout is not None:
            GLib.source_remove(self._paned_save_timeout)
        position = paned.get_position()

        def save():
            self._paned_save_timeout = None
            self.config["sidebar_paned_position"] = position
            save_config(self.config)
            return False

        self._paned_save_timeout = GLib.timeout_add(400, save)

    # --- tray / window lifecycle ---

    def on_tray_activate(self):
        if self.get_visible():
            self.set_visible(False)
        else:
            self.present()

    def on_close_request(self, _window):
        if self.quitting or not self.tray.registered:
            # No tray icon available (unsupported desktop) — closing the
            # window is the only way out, so let it actually quit rather
            # than hiding an unreachable window forever.
            return False
        self.set_visible(False)
        return True

    def on_quit_clicked(self, _button):
        self.menu_popover.popdown()
        self.quitting = True
        self.get_application().quit()

    # --- menu ---

    def on_refresh_all_clicked(self, _button):
        if self.config.get("location"):
            self.fetch_weather()
        self.fetch_backups()
        self.fetch_system_health()
        self.fetch_disk_growth()
        self.fetch_events()
        self.todo_sidebar.fetch_tasks()

    def on_preferences_clicked(self, _button):
        self.menu_popover.popdown()
        prefs = PreferencesWindow(
            self, self.config, save_config,
            on_weather_changed=self.fetch_weather,
            on_units_changed=self.render_weather,
            on_google_changed=self.on_google_account_changed,
            autostart_enabled=autostart_path().exists(),
            on_autostart_toggled=self.on_autostart_toggled,
        )
        prefs.present()

    def on_google_account_changed(self):
        self.fetch_events()
        self.todo_sidebar.fetch_tasks()

    def on_about_clicked(self, _button):
        self.menu_popover.popdown()
        about = Adw.AboutWindow(
            transient_for=self,
            application_name="Zarya",
            application_icon=APP_ID,
            version=__version__,
            developer_name="calstfrancis",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/calstfrancis/zarya",
            comments="A morning dashboard: system updates, weather, backup status, and today's events.",
            copyright="© 2026 calstfrancis",
        )
        about.present()

    def on_whats_new_clicked(self, _button):
        self.menu_popover.popdown()
        window = Adw.Window(transient_for=self, modal=True, default_width=560, default_height=680, title="What's New")

        header = Adw.HeaderBar()
        header.add_css_class("fond-chrome")
        header.set_title_widget(Adw.WindowTitle(title="What's New", subtitle=f"You're on v{__version__}"))

        body = changelog.build_view(__version__)
        clamp = Adw.Clamp(maximum_size=480)
        clamp.set_child(body)

        scrolled = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.set_child(clamp)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.set_top_bar_style(Adw.ToolbarStyle.RAISED_BORDER)
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(scrolled)
        window.set_content(toolbar_view)
        window.present()

    # --- weather ---

    def _on_weather_refresh_timer(self):
        self.fetch_weather()
        return True

    def _on_gradient_refresh_timer(self):
        styles.refresh_weather_gradient()
        self._update_window_title()
        return True

    def _update_window_title(self):
        now = datetime.datetime.now()
        self.window_title.set_title(now.strftime("%A, %B %-d"))

        hour = now.hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        pieces = [greeting]
        if self.weather_data and self.weather_data.get("label"):
            pieces.append(self.weather_data["label"].split(",")[0])

        attention = sum(
            1 for card in (self.system_card, self.backups_card, self.updates_card)
            if card.has_css_class("error") or card.has_css_class("warning")
        )
        if attention:
            verb = "needs" if attention == 1 else "need"
            pieces.append(f"{attention} thing{'s' if attention != 1 else ''} {verb} attention")
        else:
            pieces.append("all clear")
        self.window_title.set_subtitle(" · ".join(pieces))

    def fetch_weather(self):
        location = self.config.get("location", "").strip()
        if not location:
            self.weather_summary_label.set_label("Set a location in Preferences to see today's weather.")
            self.weather_current_label.set_label("")
            self.weather_aqi_label.set_label("")
            self.weather_sun_label.set_label("")
            self.weather_table.set_visible(False)
            self._clear_box(self.alerts_box)
            self._set_status_icon(self.weather_status_icon, "neutral")
            return
        self.weather_summary_label.set_label(f"Loading weather for {location}…")
        self.weather_current_label.set_label("")
        self.weather_aqi_label.set_label("")

        def worker():
            try:
                lat, lon, label = weather.geocode(location)
                today = weather.fetch_today(lat, lon)
                today["label"] = label
            except (OSError, ValueError, KeyError) as e:
                GLib.idle_add(self.on_weather_error, str(e))
                return
            try:
                today["alerts"] = weather_alerts.fetch_active_alerts(lat, lon)
            except (OSError, ValueError, KeyError):
                # Environment Canada only — this legitimately fails/returns
                # nothing for locations outside Canada, and is a bonus on
                # top of the core forecast either way, so never block on it.
                today["alerts"] = []
            try:
                today["aqi"] = weather_aqi.fetch_current_aqi(lat, lon)
            except (OSError, ValueError, KeyError):
                today["aqi"] = None
            GLib.idle_add(self.on_weather_ready, today)

        threading.Thread(target=worker, daemon=True).start()

    def on_weather_error(self, message):
        self.weather_summary_label.set_label(f"Couldn't get weather: {message}")
        self.weather_current_label.set_label("")
        self.weather_aqi_label.set_label("")
        self.weather_sun_label.set_label("")
        self.weather_table.set_visible(False)
        self._clear_box(self.alerts_box)
        self._set_status_icon(self.weather_status_icon, "error")
        return False

    def on_weather_ready(self, data):
        self.weather_data = data
        self.weather_table.set_visible(True)
        self._set_status_icon(self.weather_status_icon, "ok")
        self.render_weather()
        return False

    def render_weather(self):
        if not self.weather_data:
            return
        d = self.weather_data
        units = self.config.get("units", "celsius")
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

        if d.get("current_temp_c") is not None:
            convert = weather.celsius_to_fahrenheit if units == "fahrenheit" else (lambda c: c)
            cur = round(convert(d["current_temp_c"]))
            current_text = f"{cur}°{unit_letter}"
            if d.get("feels_like_c") is not None:
                feels = round(convert(d["feels_like_c"]))
                if feels != cur:
                    current_text += f" · feels {feels}°{unit_letter}"
            self.weather_current_label.set_label(current_text)
        else:
            self.weather_current_label.set_label("")

        for css_class in (
            "aqi-good", "aqi-moderate", "aqi-unhealthy-sensitive",
            "aqi-unhealthy", "aqi-very-unhealthy", "aqi-hazardous",
        ):
            self.weather_aqi_label.remove_css_class(css_class)
        aqi = d.get("aqi")
        if aqi:
            self.weather_aqi_label.set_label(f"AQI {aqi['value']:.0f} ({aqi['category']})")
            self.weather_aqi_label.add_css_class(aqi["css_class"])
        else:
            self.weather_aqi_label.set_label("")

        self.weather_table.set_data(d["hours"], temps, d["humidity"], d["precip_prob"], unit_letter)
        self.weather_table.center_on_now()
        self.render_alerts(d.get("alerts", []))

        sunrise = weather.format_sun_time(d.get("sunrise"))
        sunset = weather.format_sun_time(d.get("sunset"))
        sun_pieces = []
        if sunrise and sunset:
            sun_pieces.append(f"☀ {sunrise} – {sunset}")
        delta = weather.day_length_delta_minutes(
            d.get("sunrise"), d.get("sunset"), d.get("sunrise_yesterday"), d.get("sunset_yesterday"),
        )
        if delta is not None and round(delta) != 0:
            sign = "+" if delta > 0 else "−"
            sun_pieces.append(f"{sign}{abs(round(delta))}m daylight")
        moon = weather.moon_phase()
        sun_pieces.append(f"{moon['emoji']} {moon['name']} ({moon['illumination']:.0f}%)")
        self.weather_sun_label.set_label(" · ".join(sun_pieces))

        sunrise_hour, sunset_hour = weather.sun_hours(d.get("sunrise"), d.get("sunset"))
        styles.set_sun_hours(sunrise_hour, sunset_hour)
        current_code = d.get("current_code")
        styles.set_precip_tint(weather.precip_tint(current_code) if current_code is not None else None)
        self._update_window_title()

    def render_alerts(self, alerts):
        self._clear_box(self.alerts_box)
        for alert in alerts:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            css_class = {"red": "error", "orange": "warning", "yellow": "warning"}.get(alert["risk_colour"], "accent")
            icon = Gtk.Image(icon_name="dialog-warning-symbolic")
            icon.add_css_class(css_class)
            row.append(icon)

            label = Gtk.Label(label=alert["headline"], xalign=0, hexpand=True, wrap=True)
            label.add_css_class(css_class)
            if alert.get("text"):
                label.set_tooltip_text(alert["text"])
            row.append(label)

            self.alerts_box.append(row)

    # --- backups ---

    def _on_backups_refresh_timer(self):
        self.fetch_backups()
        return True

    def on_open_pereprava_clicked(self, _button):
        # "pereprava" is only on PATH for the install-script distribution
        # (~/.local/bin), and flatpak-spawn --host doesn't reliably see that
        # directory — the button silently did nothing on a flatpak install of
        # Pereprava. `flatpak run <app-id>` doesn't depend on PATH at all, and
        # matches how Zarya's own autostart entry launches itself.
        try:
            Gio.Subprocess.new(
                ["flatpak-spawn", "--host", "flatpak", "run", "io.github.calstfrancis.pereprava"],
                Gio.SubprocessFlags.NONE,
            )
        except GLib.Error as e:
            self.toast_overlay.add_toast(Adw.Toast(title=f"Couldn't open Pereprava: {e}"))

    def fetch_backups(self):
        self._set_box_message(self.backup_box, "Checking backup status…")
        backup_status.fetch_status(self.on_backup_status)

    def on_backup_status(self, jobs, error):
        if error is not None:
            self._set_box_message(self.backup_box, f"Couldn't check backup status: {error}")
            self.backups_card_value.set_label("Couldn't check")
            self.backups_card_detail.set_visible(False)
            self._set_status_severity("backups", "error")
            self._update_window_title()
            return
        if not jobs:
            self._set_box_message(self.backup_box, "No Pereprava jobs configured.")
            self.backups_card_value.set_label("Not configured")
            self.backups_card_detail.set_visible(False)
            self._set_status_severity("backups", "ok")
            self._update_window_title()
            return
        failed = [j for j in jobs if j.get("state") == "failed"]
        running = [j for j in jobs if j.get("state") == "running"]
        if failed:
            self.backups_card_value.set_label(f"{len(failed)} failed")
            self.backups_card_detail.set_label(", ".join(j.get("name", "?") for j in failed))
            self.backups_card_detail.set_visible(True)
            self._set_status_severity("backups", "error")
        elif running:
            self.backups_card_value.set_label("Running")
            self.backups_card_detail.set_label(", ".join(j.get("name", "?") for j in running))
            self.backups_card_detail.set_visible(True)
            self._set_status_severity("backups", "ok")
        else:
            self.backups_card_value.set_label("Up to date")
            self.backups_card_detail.set_label(f"{len(jobs)} job{'s' if len(jobs) != 1 else ''}")
            self.backups_card_detail.set_visible(True)
            self._set_status_severity("backups", "ok")
        self._clear_box(self.backup_box)
        for job in jobs:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            state = job.get("state", "idle")
            state_icon = Gtk.Image(icon_name=STATE_ICONS.get(state, "action-unavailable-symbolic"))
            state_icon.add_css_class(STATE_COLORS.get(state, "dim-label"))
            row.append(state_icon)
            name_label = Gtk.Label(label=job.get("name", "?"), xalign=0, hexpand=True)
            row.append(name_label)
            state_label = Gtk.Label(label=STATE_LABELS.get(state, state))
            state_label.add_css_class(STATE_COLORS.get(state, "dim-label"))
            row.append(state_label)
            last_run_text = self._format_backup_time(job.get("last_run")) or job.get("last_run_text")
            if last_run_text:
                last_run_label = Gtk.Label(label=f"last {last_run_text}")
                last_run_label.add_css_class("dim-label")
                row.append(last_run_label)
            next_run_text = self._format_backup_time(job.get("next_run"))
            if next_run_text:
                next_run_label = Gtk.Label(label=f"next {next_run_text}")
                next_run_label.add_css_class("dim-label")
                row.append(next_run_label)
            self.backup_box.append(row)
        self._update_window_title()

    @staticmethod
    def _format_backup_time(epoch_micros):
        if not isinstance(epoch_micros, (int, float)) or epoch_micros <= 0:
            return None
        try:
            dt = datetime.datetime.fromtimestamp(epoch_micros / 1_000_000)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (OverflowError, OSError, ValueError):
            return None

    # --- disk growth ---

    def _on_disk_growth_refresh_timer(self):
        self.fetch_disk_growth()
        return True

    def fetch_disk_growth(self):
        self._set_box_message(self.disk_growth_box, "Measuring home directory sizes…")
        disk_growth.fetch_sizes(self.on_disk_growth_ready)

    def on_disk_growth_ready(self, sizes, error):
        if error is not None:
            self._set_box_message(self.disk_growth_box, f"Couldn't measure disk growth: {error}")
            return
        if not sizes:
            self._set_box_message(self.disk_growth_box, "No home directories found to measure.")
            return
        history = disk_growth.record_snapshot(sizes)
        rows, has_baseline = disk_growth.growth_since(history, sizes)
        self._clear_box(self.disk_growth_box)
        if not has_baseline:
            note = Gtk.Label(
                label="Collecting a week of history before showing growth — check back soon.",
                xalign=0, wrap=True,
            )
            note.add_css_class("dim-label")
            self.disk_growth_box.append(note)
            return
        growing = [r for r in rows if r[2] > 0][:5]
        if not growing:
            self._set_box_message(self.disk_growth_box, "Nothing has grown noticeably in the last week.")
            return
        for name, current, delta in growing:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            icon = Gtk.Image(icon_name="folder-symbolic")
            icon.add_css_class("dim-label")
            row.append(icon)
            name_label = Gtk.Label(label=name, xalign=0, hexpand=True)
            row.append(name_label)
            size_label = Gtk.Label(label=self._format_bytes(current))
            size_label.add_css_class("dim-label")
            row.append(size_label)
            delta_label = Gtk.Label(label=f"+{self._format_bytes(delta)} this week")
            delta_label.add_css_class("warning")
            row.append(delta_label)
            self.disk_growth_box.append(row)

    # --- habits ---

    def on_add_habit_clicked(self, _button):
        entry = Adw.EntryRow(title="Habit name")
        dialog = Adw.AlertDialog(heading="Add a Habit", body="What do you want to track daily?")
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Add")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("add")
        dialog.set_close_response("cancel")

        def on_response(_dialog, response):
            if response == "add":
                name = entry.get_text().strip()
                if name:
                    data = habits.load()
                    habits.add_habit(data, name)
                    self.render_habits()

        dialog.connect("response", on_response)
        dialog.present(self)

    def on_habit_toggle_clicked(self, button, name):
        data = habits.load()
        habits.toggle_today(data, name)
        self.render_habits()

    def on_habit_remove_clicked(self, _button, name):
        data = habits.load()
        habits.remove_habit(data, name)
        self.render_habits()

    def render_habits(self):
        self._clear_box(self.habits_box)
        data = habits.load()
        if not data["habits"]:
            note = Gtk.Label(label="No habits yet — click + to add one.", xalign=0, wrap=True)
            note.add_css_class("dim-label")
            self.habits_box.append(note)
            return
        for name in data["habits"]:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.add_css_class("fond-statusbar")

            toggle = Gtk.Button(label=name, has_frame=False, hexpand=True)
            toggle.get_child().set_xalign(0)
            done = habits.is_done_today(data, name)
            if done:
                toggle.add_css_class("fond-toggle-active")
            toggle.set_tooltip_text("Mark done for today" if not done else "Marked done today — click to undo")
            toggle.connect("clicked", self.on_habit_toggle_clicked, name)
            row.append(toggle)

            week = habits.week_count(data, name)
            week_label = Gtk.Label(label=f"{week}/7 this week")
            week_label.add_css_class("dim-label")
            row.append(week_label)

            streak = habits.current_streak(data, name)
            if streak > 0:
                streak_label = Gtk.Label(label=f"🔥 {streak}d")
                streak_label.add_css_class("dim-label")
                row.append(streak_label)

            remove_button = Gtk.Button(icon_name="edit-delete-symbolic", has_frame=False, opacity=0)
            remove_button.set_tooltip_text(f"Remove {name}")
            remove_button.connect("clicked", self.on_habit_remove_clicked, name)
            row.append(remove_button)
            _wire_hover_reveal(row, remove_button)

            self.habits_box.append(row)

    # --- system health ---

    def _on_health_refresh_timer(self):
        self.fetch_system_health()
        return True

    def fetch_system_health(self):
        self._set_box_message(self.health_box, "Checking system health…")
        self._health_disks = None
        self._health_disks_error = None
        self._health_drives = None
        self._health_drives_error = None
        self._health_batteries = None
        self._health_batteries_error = None
        self._health_thermal = None
        self._health_thermal_error = None
        system_health.fetch_disk_usage(self._on_disk_usage_ready)
        system_health.fetch_thermal_health(self._on_thermal_health_ready)
        threading.Thread(target=self._fetch_smart_health_worker, daemon=True).start()
        threading.Thread(target=self._fetch_battery_health_worker, daemon=True).start()

    def _fetch_smart_health_worker(self):
        try:
            drives = system_health.fetch_smart_health()
        except GLib.Error as e:
            GLib.idle_add(self._on_smart_health_ready, None, str(e))
            return
        GLib.idle_add(self._on_smart_health_ready, drives, None)

    def _fetch_battery_health_worker(self):
        try:
            batteries = system_health.fetch_battery_health()
        except GLib.Error as e:
            GLib.idle_add(self._on_battery_health_ready, None, str(e))
            return
        GLib.idle_add(self._on_battery_health_ready, batteries, None)

    def _on_disk_usage_ready(self, disks, error):
        self._health_disks = disks if disks is not None else []
        self._health_disks_error = error
        self._render_system_health()
        return False

    def _on_smart_health_ready(self, drives, error):
        self._health_drives = drives if drives is not None else []
        self._health_drives_error = error
        self._render_system_health()
        return False

    def _on_battery_health_ready(self, batteries, error):
        self._health_batteries = batteries if batteries is not None else []
        self._health_batteries_error = error
        self._render_system_health()
        return False

    def _on_thermal_health_ready(self, readings, error):
        self._health_thermal = readings if readings is not None else []
        self._health_thermal_error = error
        self._render_system_health()
        return False

    def _render_system_health(self):
        disks_done = self._health_disks is not None or self._health_disks_error is not None
        drives_done = self._health_drives is not None or self._health_drives_error is not None
        batteries_done = self._health_batteries is not None or self._health_batteries_error is not None
        thermal_done = self._health_thermal is not None or self._health_thermal_error is not None
        if not (disks_done and drives_done and batteries_done and thermal_done):
            return

        self._clear_box(self.health_box)
        any_problem = False
        any_row = False
        problem_texts = []
        healthy_bits = []

        if self._health_disks_error:
            error_label = Gtk.Label(label=f"Couldn't check disk space: {self._health_disks_error}", xalign=0, wrap=True)
            error_label.add_css_class("dim-label")
            self.health_box.append(error_label)
        else:
            for disk in self._health_disks:
                any_row = True
                total, used = disk["total"], disk["used"]
                pct = (used / total * 100) if total else 0
                critical = pct >= 95
                warning = pct >= 85
                any_problem = any_problem or critical
                if critical or warning:
                    problem_texts.append(f"{disk['path']} is {pct:.0f}% full")
                else:
                    healthy_bits.append(f"{disk['path']} {pct:.0f}% full")
                if critical:
                    icon_name, css_class = "dialog-error-symbolic", "error"
                elif warning:
                    icon_name, css_class = "dialog-warning-symbolic", "warning"
                else:
                    icon_name, css_class = "drive-harddisk-symbolic", "dim-label"
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                icon = Gtk.Image(icon_name=icon_name)
                icon.add_css_class(css_class)
                row.append(icon)
                label = Gtk.Label(
                    label=f"{disk['path']} — {self._format_bytes(used)} / {self._format_bytes(total)} ({pct:.0f}%)",
                    xalign=0, hexpand=True,
                )
                row.append(label)
                self.health_box.append(row)

        if self._health_drives_error:
            error_label = Gtk.Label(label=f"Couldn't check drive health: {self._health_drives_error}", xalign=0, wrap=True)
            error_label.add_css_class("dim-label")
            self.health_box.append(error_label)
        else:
            healthy_drive_count = 0
            for drive in self._health_drives:
                any_row = True
                any_problem = any_problem or not drive["healthy"]
                if drive["healthy"]:
                    healthy_drive_count += 1
                else:
                    problem_texts.append(f"{drive['model']} — {drive['detail']}")
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                icon = Gtk.Image(icon_name="emblem-ok-symbolic" if drive["healthy"] else "dialog-error-symbolic")
                icon.add_css_class("success" if drive["healthy"] else "error")
                row.append(icon)
                label = Gtk.Label(label=f"{drive['model']} — {drive['detail']}", xalign=0, hexpand=True)
                row.append(label)
                self.health_box.append(row)
            if healthy_drive_count:
                healthy_bits.append(f"{healthy_drive_count} drive{'s' if healthy_drive_count != 1 else ''} healthy")

        if self._health_batteries_error:
            error_label = Gtk.Label(label=f"Couldn't check battery health: {self._health_batteries_error}", xalign=0, wrap=True)
            error_label.add_css_class("dim-label")
            self.health_box.append(error_label)
        else:
            for battery in self._health_batteries:
                any_row = True
                capacity = battery.get("capacity")
                critical = capacity is not None and capacity < 60
                warning = capacity is not None and capacity < 80
                any_problem = any_problem or critical
                if critical or warning:
                    problem_texts.append(f"Battery health at {capacity:.0f}%")
                if critical:
                    icon_name, css_class = "dialog-error-symbolic", "error"
                elif warning:
                    icon_name, css_class = "dialog-warning-symbolic", "warning"
                else:
                    icon_name, css_class = "battery-good-symbolic", "dim-label"
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                icon = Gtk.Image(icon_name=icon_name)
                icon.add_css_class(css_class)
                row.append(icon)
                text = f"Battery — {battery.get('percentage', 0):.0f}% charged"
                if capacity is not None:
                    text += f", {capacity:.0f}% battery health"
                if battery.get("cycles"):
                    text += f" ({battery['cycles']} cycles)"
                label = Gtk.Label(label=text, xalign=0, hexpand=True)
                row.append(label)
                self.health_box.append(row)
                # No battery present (most desktops) isn't an error, and
                # isn't reported at all — nothing meaningful to show.

        if self._health_thermal_error:
            error_label = Gtk.Label(label=f"Couldn't check temperatures: {self._health_thermal_error}", xalign=0, wrap=True)
            error_label.add_css_class("dim-label")
            self.health_box.append(error_label)
        else:
            for reading in self._health_thermal:
                any_row = True
                celsius = reading["celsius"]
                critical = celsius >= 95
                warning = celsius >= 85
                any_problem = any_problem or critical
                kind_label = "CPU" if reading["kind"] == "cpu" else "GPU"
                if critical or warning:
                    problem_texts.append(f"{kind_label} at {celsius:.0f}°C")
                else:
                    healthy_bits.append(f"{kind_label} {celsius:.0f}°C")
                if critical:
                    icon_name, css_class = "dialog-error-symbolic", "error"
                elif warning:
                    icon_name, css_class = "dialog-warning-symbolic", "warning"
                else:
                    icon_name, css_class = "emblem-ok-symbolic", "dim-label"
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                icon = Gtk.Image(icon_name=icon_name)
                icon.add_css_class(css_class)
                row.append(icon)
                label = Gtk.Label(
                    label=f"{kind_label} — {celsius:.0f}°C",
                    xalign=0, hexpand=True,
                )
                row.append(label)
                self.health_box.append(row)
                # No hwmon chip we recognize (VM, unusual hardware) isn't
                # an error — nothing meaningful to show, same as batteries.

        if (
            not any_row and not self._health_disks_error and not self._health_drives_error
            and not self._health_batteries_error and not self._health_thermal_error
        ):
            self._set_box_message(self.health_box, "No disk or drive health data available.")

        any_error = (
            self._health_disks_error or self._health_drives_error
            or self._health_batteries_error or self._health_thermal_error
        )
        if any_problem:
            self.system_card_value.set_label("Needs attention")
            self.system_card_detail.set_label(" · ".join(problem_texts) or "See details")
            self.system_card_detail.set_visible(True)
            self._set_status_severity("system", "error")
        elif any_error:
            self.system_card_value.set_label("Partly checked")
            self.system_card_detail.set_visible(False)
            self._set_status_severity("system", "ok")
        else:
            self.system_card_value.set_label("Healthy")
            self.system_card_detail.set_label(" · ".join(healthy_bits) if healthy_bits else "")
            self.system_card_detail.set_visible(bool(healthy_bits))
            self._set_status_severity("system", "ok")
        self._update_window_title()

    @staticmethod
    def _format_bytes(n):
        value = float(n)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} TB"

    # --- calendar ---

    def _on_events_refresh_timer(self):
        self.fetch_events()
        return True

    def fetch_events(self):
        refresh_token = keyring.lookup_google_refresh_token()
        if not refresh_token:
            self._set_box_message(self.events_box, "Connect your Google Account in Preferences to see today's events.")
            self._set_status_icon(self.events_status_icon, "neutral")
            return
        self._set_box_message(self.events_box, "Loading today's events…")

        def worker():
            try:
                events = google_calendar.fetch_today_events(refresh_token, self.config.get("calendar_ids"))
            except (OSError, ValueError, KeyError) as e:
                GLib.idle_add(self.on_events_error, str(e))
                return
            GLib.idle_add(self.on_events_ready, events)

        threading.Thread(target=worker, daemon=True).start()

    def on_events_error(self, message):
        self._set_box_message(self.events_box, f"Couldn't load events: {message}")
        self._set_status_icon(self.events_status_icon, "error")
        return False

    def on_events_ready(self, events):
        self._set_status_icon(self.events_status_icon, "ok")
        if not events:
            self._set_box_message(self.events_box, "No events today.")
            return False
        self._clear_box(self.events_box)
        now = datetime.datetime.now()
        now_line_inserted = False

        for event in events:
            is_past = False
            if not event["all_day"]:
                end = event.get("end") or event["start"]
                is_past = end < now
                if not now_line_inserted and event["start"] >= now:
                    self.events_box.append(self._make_now_line(now))
                    now_line_inserted = True

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

            time_text = "All day" if event["all_day"] else event["start"].strftime("%I:%M %p").lstrip("0")
            time_label = Gtk.Label(label=time_text)
            time_label.add_css_class("dim-label")
            time_label.set_width_chars(8)
            time_label.set_xalign(0)
            row.append(time_label)

            dot = Gtk.Box(width_request=8, height_request=8, valign=Gtk.Align.CENTER)
            dot.add_css_class(f"cal-dot-{hash(event.get('calendar_id', '')) % 6}")
            row.append(dot)

            summary_label = Gtk.Label(label=event["summary"], xalign=0, hexpand=True, wrap=True)
            if is_past:
                summary_label.add_css_class("dim-label")
                row.set_opacity(0.55)
            row.append(summary_label)
            self.events_box.append(row)

        return False

    @staticmethod
    def _make_now_line(now):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, margin_top=2, margin_bottom=2)
        time_label = Gtk.Label(label=now.strftime("%I:%M").lstrip("0"))
        time_label.add_css_class("now-marker-label")
        time_label.add_css_class("caption")
        time_label.set_width_chars(8)
        time_label.set_xalign(0)
        row.append(time_label)
        line = Gtk.Box(hexpand=True, valign=Gtk.Align.CENTER)
        line.add_css_class("now-marker-line")
        row.append(line)
        return row

    # --- shared helpers ---

    @staticmethod
    def _clear_box(box):
        child = box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            box.remove(child)
            child = next_child

    def _set_box_message(self, box, message):
        self._clear_box(box)
        box.append(Gtk.Label(label=message, xalign=0, wrap=True))

    def log(self, text):
        end = self.buffer.get_end_iter()
        self.buffer.insert(end, text)
        self.text_view.scroll_to_iter(self.buffer.get_end_iter(), 0.0, False, 0, 0)

    def logline(self, text):
        text = text.rstrip("\n") + "\n"
        start_offset = self.buffer.get_end_iter().get_offset()
        self.log(text)
        lower = text.lower()
        tag = None
        if "failed" in lower or "error" in lower or "cancelling" in lower:
            tag = self.log_error_tag
        elif "all done" in lower:
            tag = self.log_success_tag
        if tag is not None:
            start_iter = self.buffer.get_iter_at_offset(start_offset)
            self.buffer.apply_tag(tag, start_iter, self.buffer.get_end_iter())

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

    def already_reported_timer_failure_today(self):
        path = timer_failure_marker_path()
        if not path.exists():
            return False
        return path.read_text().strip() == self.today_str()

    def mark_timer_failure_reported(self):
        path = timer_failure_marker_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.today_str())

    def _set_status_text(self, text):
        self.status_label.set_label(text)
        self.updates_card_value.set_label(text)
        self.updates_card_detail.set_visible(False)
        self._set_status_severity("updates", "ok")

    def refresh_status(self):
        if self.already_ran_today():
            self.status_label.set_label("Already updated today")
            self.run_button.set_label("Run Anyway")
        else:
            self.status_label.set_label("Ready to update")
            self.run_button.set_label("Run Now")

        result = load_result()
        for css_class in ("success", "error"):
            self.result_label.remove_css_class(css_class)
        if result is None:
            self.result_icon.set_from_icon_name("dialog-question-symbolic")
            self.result_label.set_label("No update has run yet")
            self.updates_card_value.set_label("Never run")
            self.updates_card_detail.set_visible(False)
            self._set_status_severity("updates", "ok")
        elif result.get("success"):
            self.result_icon.set_from_icon_name("emblem-ok-symbolic")
            self.result_label.set_label(f"Last update succeeded at {result.get('time', '?')}")
            self.result_label.add_css_class("success")
            self.updates_card_value.set_label("Up to date")
            self.updates_card_detail.set_label(f"Ran {result.get('time', '?')}")
            self.updates_card_detail.set_visible(True)
            self._set_status_severity("updates", "ok")
        else:
            self.result_icon.set_from_icon_name("dialog-error-symbolic")
            self.result_label.set_label(f"Last update failed at {result.get('time', '?')}")
            self.result_label.add_css_class("error")
            self.updates_card_value.set_label("Failed")
            self.updates_card_detail.set_label(f"At {result.get('time', '?')} — Run Anyway to retry")
            self.updates_card_detail.set_visible(True)
            self._set_status_severity("updates", "error")

        self.render_history()
        self._update_window_title()

    def render_history(self):
        child = self.history_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.history_box.remove(child)
            child = next_child
        history = load_history()
        self.history_row.set_visible(bool(history))
        for entry in history:
            dot = Gtk.Image(icon_name="media-record-symbolic", pixel_size=10)
            dot.add_css_class("success" if entry.get("success") else "error")
            dot.set_tooltip_text(f"{entry.get('date', '?')}: {'succeeded' if entry.get('success') else 'failed'}")
            self.history_box.append(dot)

    def on_autostart_toggled(self, enabled):
        """Called from Preferences > Updates' "Start at login" switch."""
        path = autostart_path()
        try:
            if enabled:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(AUTOSTART_CONTENT)
            else:
                path.unlink(missing_ok=True)
        except OSError as e:
            self.toast_overlay.add_toast(Adw.Toast(title=f"Couldn't update autostart: {e}"))

    def on_run_clicked(self, _button):
        if self.proc is not None:
            return
        self.start_updates()

    def on_cancel_clicked(self, _button):
        if self.proc is None:
            return
        self.logline("")
        self.logline("--- cancelling… ---")
        if self._phase == "checking":
            # Just the async systemd status check running — nothing external
            # started yet, and it finishes on its own in well under a second.
            return
        proc = self.proc
        try:
            # SIGTERM, not force_exit()/SIGKILL: the real command runs on the
            # *host*, reached via flatpak-spawn --host. SIGKILL can never be
            # caught, so it only kills the local flatpak-spawn wrapper — the
            # host-side pkexec/zypper process would be orphaned and keep
            # running invisibly, and could hold the zypper lock for a
            # subsequent "Run Anyway". SIGTERM is catchable, so flatpak-spawn
            # forwards it to the host process (and pkexec forwards it again
            # to its child) before this process exits.
            proc.send_signal(15)
        except GLib.Error as e:
            self.logline(f"[cancel error: {e}]")
            return
        GLib.timeout_add(5000, self._force_kill_if_still_running, proc)

    def _force_kill_if_still_running(self, proc):
        if self.proc is proc:
            self.logline("[still running 5s after cancelling — forcing it]")
            try:
                proc.force_exit()
            except GLib.Error:
                pass
        return False

    def _set_running(self, running):
        self.run_button.set_sensitive(not running)
        self.cancel_button.set_sensitive(running)

    _ZYPPER_DONE_MARKER = "__ZARYA_ZYPPER_DONE__"

    def start_updates(self, interactive=True):
        """interactive=True (the "Run Now" button): always completes today's
        update, prompting via pkexec if the privileged part hasn't already
        been done today by the root timer (see system_updates.py and
        zarya/CLAUDE.md) — this is a deliberate manual click, so a password
        prompt here is normal and expected, same as it always was.

        interactive=False (the silent background poll, _maybe_autorun): NEVER
        prompts. If the root timer already did the privileged part today, it
        finishes the loop with the unprivileged flatpak --user step and marks
        the day done, silently. If the timer hasn't run yet, it does nothing
        and waits for the next poll — Zarya itself no longer force-triggers
        a password prompt in the background, which was the actual complaint
        Preferences > Updates' timer exists to fix."""
        if self.proc is not None:
            return
        self.buffer.set_text("")
        self.proc = True  # busy sentinel until the async status check resolves
        self._phase = "checking"
        self._interactive = interactive
        self._set_running(interactive)
        if interactive:
            self._set_status_text("Checking…")
        self.logline(f"=== Zarya update: {self.today_str()} ===")
        self.logline("")
        if interactive and self.already_ran_today():
            # "Run Anyway": Zarya's own marker already says today is done,
            # so this is a deliberate forced re-run — skip the "did the
            # timer already do this" dedup check entirely. That check exists
            # to spare a redundant password prompt on the day's *first*
            # click when the root timer got there first, not to silently
            # water down an explicit "do it again" request into a no-op.
            self._on_daily_status_checked(False, False, False)
            return
        _check_unit_already_ran_today(self._on_daily_status_checked)

    def _on_daily_status_checked(self, ran_today, succeeded_today, failed_today):
        if ran_today and succeeded_today:
            self.logline("--- system update already completed today (daily timer) — skipping ---")
            self.on_privileged_done(True, 0)
            return
        if not self._interactive:
            if failed_today and not self.already_reported_timer_failure_today():
                # The timer's own retries (Restart= in zarya-system-update.service)
                # are exhausted and today's run is genuinely, finally failed
                # — not just between attempts. Record that once, so a failed
                # automatic day isn't silently invisible on the dashboard
                # (Preferences > Updates shows it too, but not everyone
                # thinks to go check there). Deliberately not mark_done() —
                # "Run Now" should stay available, not flip to "Run Anyway",
                # since nothing actually succeeded yet today.
                self.mark_timer_failure_reported()
                self.logline("--- daily timer update failed after retries — see /var/log/zarya-system-update.log ---")
                self.finish(success=False)
                return
            # Otherwise: hasn't run yet, still working through its own
            # retries, or already reported — Zarya doesn't prompt or retry
            # on its own either way; either the timer catches up, or Cal
            # clicks Run Now.
            self.proc = None
            self._phase = None
            self._set_running(False)
            return
        self._system_flatpak_retried = False
        self._saw_hidden_marker = False
        self._phase = "privileged"
        self._set_status_text("Updating…")
        self.logline("--- zypper refresh + dist-upgrade + system flatpaks (enter your password when prompted) ---")
        self.run_step(
            [
                "flatpak-spawn", "--host", "pkexec", "sh", "-c",
                f"zypper ref && zypper dup -y && echo {self._ZYPPER_DONE_MARKER} && flatpak update --system -y",
            ],
            self.on_privileged_done,
            hidden_marker=self._ZYPPER_DONE_MARKER,
        )

    def on_privileged_done(self, success, exit_status):
        self.logline("")
        if not success:
            zypper_succeeded = self._saw_hidden_marker
            if zypper_succeeded and not self._system_flatpak_retried:
                # zypper itself finished fine — this is specifically the
                # system flatpak update failing, which Cal has seen happen
                # intermittently (looked like the polkit authorization from
                # the same pkexec session going stale by the time zypper's
                # dup finished and control reached this step). One retry,
                # with a fresh pkexec call, since we don't otherwise know
                # whether it's transient.
                self._system_flatpak_retried = True
                self.logline("zypper succeeded, but the system flatpak update failed — retrying it once...")
                self.run_step(
                    ["flatpak-spawn", "--host", "pkexec", "flatpak", "update", "--system", "-y"],
                    self.on_privileged_done,
                )
                return
            self.logline(f"zypper/system-flatpak step failed (exit status {exit_status}).")
            self.finish(success=False)
            return
        self._phase = "unprivileged"
        if self._interactive:
            self._set_status_text("Updating…")
        self.logline("--- flatpak update (user installs) ---")
        self.run_step(
            ["flatpak-spawn", "--host", "flatpak", "update", "--user", "-y"],
            self.on_flatpak_done,
        )

    def on_flatpak_done(self, success, exit_status):
        self.logline("")
        if not success:
            self.logline(f"flatpak update failed (exit status {exit_status}).")
        self.finish(success=success)

    def finish(self, success):
        self.proc = None
        self._phase = None
        self._set_running(False)
        save_result(success)
        append_history(success)

        summary = None
        if success:
            self.mark_done()
            full_text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)
            summary = summarize_updates(full_text)
            if summary:
                self.logline(f"Summary: {summary}")
            self.logline("All done.")
            self.maybe_offer_restart(full_text)
        else:
            self.logline("Not marking today as done — you can retry with Run Anyway.")

        self.send_result_notification(success, summary)
        self.refresh_status()

    def maybe_offer_restart(self, full_text):
        # Best-effort, same spirit as summarize_updates(): a substring match
        # on Zarya's own app ID in the update log's "Updating: ..." flatpak
        # output — good enough to know Zarya itself was among the packages
        # updated, without needing to diff installed versions before/after.
        # Matters because a flatpak update only replaces files on disk — the
        # already-running process (this one) keeps executing its old code
        # in memory until it's actually restarted. A banner across the top
        # of the window rather than a modal dialog — less disruptive if this
        # fires from the silent background autorun while Cal is mid-task,
        # and it stays visible (not auto-dismissed) until acted on or the
        # window is next closed.
        if APP_ID not in full_text:
            return
        if not self.get_visible():
            self.present()
        self.restart_banner.set_revealed(True)

    def restart_now(self):
        try:
            Gio.Subprocess.new(
                ["flatpak-spawn", "--host", "flatpak", "run", APP_ID],
                Gio.SubprocessFlags.NONE,
            )
        except GLib.Error as e:
            self.toast_overlay.add_toast(Adw.Toast(title=f"Couldn't restart Zarya: {e}"))
            return
        self.quitting = True
        self.get_application().quit()

    def send_result_notification(self, success, summary):
        app = self.get_application()
        if app is None:
            return
        notification = Gio.Notification.new("Zarya")
        if success:
            body = "Update completed successfully."
            if summary:
                body += f" {summary}"
            notification.set_body(body)
            notification.set_icon(Gio.ThemedIcon.new("emblem-ok-symbolic"))
        else:
            notification.set_body("Update failed — open Zarya to see the log.")
            notification.set_icon(Gio.ThemedIcon.new("dialog-error-symbolic"))
        app.send_notification("zarya-update", notification)

    def run_step(self, argv, done_callback, hidden_marker=None):
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
        self._pump_output(stream, hidden_marker)
        proc.wait_async(None, self._on_wait, done_callback)

    def _pump_output(self, stream, hidden_marker=None):
        def on_line(source, result):
            try:
                line, _length = source.read_line_finish_utf8(result)
            except GLib.Error:
                return
            if line is None:
                return
            if hidden_marker is not None and line.strip() == hidden_marker:
                # An internal progress marker, not real command output —
                # record it without cluttering the visible log.
                self._saw_hidden_marker = True
            else:
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
        self.start_hidden = False
        self.add_main_option(
            "background", 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
            "Start hidden in the tray (used by the autostart entry)", None,
        )
        self.connect("handle-local-options", self._on_handle_local_options)

    def _on_handle_local_options(self, _app, options):
        self.start_hidden = options.contains("background")
        return -1

    def do_activate(self):
        first_launch = self.window is None
        if first_launch:
            styles.apply()
            self.hold()
            self.window = ZaryaWindow(self)
            if not self.start_hidden:
                self.window.present()
            if self.window.config.get("onboarded"):
                if not self.window.already_ran_today():
                    GLib.idle_add(self.window.start_updates)
            else:
                # Silent first-run setup doesn't make sense — show it
                # regardless of --background.
                self.window.present()
                onboarding = OnboardingWindow(
                    self.window, self.window.config, save_config,
                    on_finished=self.on_onboarding_finished,
                )
                onboarding.present()
        else:
            self.window.present()

    def on_onboarding_finished(self):
        if not autostart_path().exists():
            try:
                autostart_path().parent.mkdir(parents=True, exist_ok=True)
                autostart_path().write_text(AUTOSTART_CONTENT)
            except OSError:
                pass
        self.window.fetch_weather()
        self.window.fetch_events()
        self.window.todo_sidebar.fetch_tasks()
        if not self.window.already_ran_today():
            GLib.idle_add(self.window.start_updates)


def main():
    app = ZaryaApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
