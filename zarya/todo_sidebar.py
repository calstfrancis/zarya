import threading

from gi.repository import GLib, Gtk

from . import google_tasks, keyring


class TodoSidebar(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.tasks = []
        self.set_size_request(240, -1)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(8)
        self.set_margin_end(12)

        card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8, vexpand=True,
            margin_top=10, margin_bottom=10, margin_start=10, margin_end=10,
        )
        card.add_css_class("fondwave-terminal")
        card.add_css_class("card")

        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title = Gtk.Label(label="To-Do", xalign=0, hexpand=True)
        title.add_css_class("title-4")
        header_row.append(title)
        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", has_frame=False)
        refresh_button.set_tooltip_text("Refresh tasks")
        refresh_button.connect("clicked", lambda *_: self.fetch_tasks())
        header_row.append(refresh_button)
        card.append(header_row)

        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.entry = Gtk.Entry(placeholder_text="Add a task…", hexpand=True)
        self.entry.connect("activate", self.on_add)
        entry_row.append(self.entry)
        self.add_button = Gtk.Button(icon_name="list-add-symbolic", has_frame=False)
        self.add_button.set_tooltip_text("Add task")
        self.add_button.connect("clicked", self.on_add)
        entry_row.append(self.add_button)
        card.append(entry_row)

        self.status_label = Gtk.Label(xalign=0, wrap=True)
        self.status_label.add_css_class("dim-label")
        self.status_label.set_visible(False)
        card.append(self.status_label)

        scroller = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        scroller.set_child(self.list_box)
        card.append(scroller)

        self.append(card)
        self.fetch_tasks()

    @staticmethod
    def _refresh_token():
        return keyring.lookup_google_refresh_token()

    def fetch_tasks(self):
        refresh_token = self._refresh_token()
        if not refresh_token:
            self.tasks = []
            self.entry.set_sensitive(False)
            self.add_button.set_sensitive(False)
            self._set_status("Connect your Google Account in Preferences to sync tasks.")
            self.render()
            return
        self.entry.set_sensitive(True)
        self.add_button.set_sensitive(True)
        self._set_status("Loading tasks…")

        def worker():
            try:
                tasks = google_tasks.list_tasks(refresh_token)
            except (OSError, ValueError, KeyError) as e:
                GLib.idle_add(self._on_fetch_error, str(e))
                return
            GLib.idle_add(self._on_fetch_ready, tasks)

        threading.Thread(target=worker, daemon=True).start()

    def _on_fetch_error(self, message):
        self._set_status(f"Couldn't load tasks: {message}")
        return False

    def _on_fetch_ready(self, tasks):
        self.tasks = tasks
        self._set_status(None)
        self.render()
        return False

    def _set_status(self, message):
        if message:
            self.status_label.set_label(message)
            self.status_label.set_visible(True)
        else:
            self.status_label.set_visible(False)

    def on_add(self, _widget):
        text = self.entry.get_text().strip()
        if not text:
            return
        refresh_token = self._refresh_token()
        if not refresh_token:
            return
        self.entry.set_sensitive(False)
        self.add_button.set_sensitive(False)

        def worker():
            try:
                task = google_tasks.add_task(refresh_token, text)
            except (OSError, ValueError, KeyError) as e:
                GLib.idle_add(self._on_add_error, str(e))
                return
            GLib.idle_add(self._on_add_ready, task)

        threading.Thread(target=worker, daemon=True).start()

    def _on_add_error(self, message):
        self.entry.set_sensitive(True)
        self.add_button.set_sensitive(True)
        self._set_status(f"Couldn't add task: {message}")
        return False

    def _on_add_ready(self, task):
        self.entry.set_text("")
        self.entry.set_sensitive(True)
        self.add_button.set_sensitive(True)
        self.tasks.append(task)
        self._set_status(None)
        self.render()
        return False

    def on_toggle(self, check_button, task):
        refresh_token = self._refresh_token()
        if not refresh_token:
            return
        done = check_button.get_active()
        task["done"] = done
        self.render()

        def worker():
            try:
                google_tasks.set_task_done(refresh_token, task["id"], done)
            except (OSError, ValueError, KeyError) as e:
                GLib.idle_add(self._on_mutation_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def on_remove(self, task):
        refresh_token = self._refresh_token()
        if not refresh_token:
            return
        self.tasks = [t for t in self.tasks if t["id"] != task["id"]]
        self.render()

        def worker():
            try:
                google_tasks.delete_task(refresh_token, task["id"])
            except (OSError, ValueError, KeyError) as e:
                GLib.idle_add(self._on_mutation_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_mutation_error(self, message):
        self._set_status(f"Sync error: {message} — refreshing…")
        self.fetch_tasks()
        return False

    def render(self):
        child = self.list_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.list_box.remove(child)
            child = next_child

        if not self.tasks:
            if self._refresh_token():
                empty_label = Gtk.Label(label="No tasks yet — add one above.", xalign=0, wrap=True)
                empty_label.add_css_class("dim-label")
                self.list_box.append(empty_label)
            return

        for task in self.tasks:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            check = Gtk.CheckButton(active=task.get("done", False))
            check.set_tooltip_text("Mark not done" if task.get("done") else "Mark done")
            check.connect("toggled", self.on_toggle, task)
            row.append(check)

            text = task.get("text", "")
            label = Gtk.Label(xalign=0, hexpand=True, wrap=True)
            if task.get("done"):
                label.add_css_class("dim-label")
                label.set_markup(f"<s>{GLib.markup_escape_text(text)}</s>")
            else:
                label.set_label(text)
            row.append(label)

            remove_button = Gtk.Button(icon_name="edit-delete-symbolic", has_frame=False)
            remove_button.set_tooltip_text("Remove")
            remove_button.connect("clicked", lambda _b, t=task: self.on_remove(t))
            row.append(remove_button)

            self.list_box.append(row)
