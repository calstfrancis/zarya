from gi.repository import GLib, Gtk


class TodoSidebar(Gtk.Box):
    def __init__(self, config, save_config):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.config = config
        self.save_config = save_config
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

        title = Gtk.Label(label="To-Do", xalign=0)
        title.add_css_class("title-4")
        card.append(title)

        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.entry = Gtk.Entry(placeholder_text="Add a task…", hexpand=True)
        self.entry.connect("activate", self.on_add)
        entry_row.append(self.entry)
        add_button = Gtk.Button(icon_name="list-add-symbolic", has_frame=False)
        add_button.set_tooltip_text("Add task")
        add_button.connect("clicked", self.on_add)
        entry_row.append(add_button)
        card.append(entry_row)

        scroller = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        scroller.set_child(self.list_box)
        card.append(scroller)

        self.append(card)
        self.render()

    def _todos(self):
        return self.config.setdefault("todos", [])

    def on_add(self, _widget):
        text = self.entry.get_text().strip()
        if not text:
            return
        self._todos().append({"text": text, "done": False})
        self.save_config(self.config)
        self.entry.set_text("")
        self.render()

    def on_toggle(self, check_button, index):
        todos = self._todos()
        if index >= len(todos):
            return
        todos[index]["done"] = check_button.get_active()
        self.save_config(self.config)
        self.render()

    def on_remove(self, index):
        todos = self._todos()
        if index >= len(todos):
            return
        todos.pop(index)
        self.save_config(self.config)
        self.render()

    def render(self):
        child = self.list_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.list_box.remove(child)
            child = next_child

        todos = self._todos()
        if not todos:
            empty_label = Gtk.Label(label="No tasks yet — add one above.", xalign=0, wrap=True)
            empty_label.add_css_class("dim-label")
            self.list_box.append(empty_label)
            return

        for index, item in enumerate(todos):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            check = Gtk.CheckButton(active=item.get("done", False))
            check.set_tooltip_text("Mark not done" if item.get("done") else "Mark done")
            check.connect("toggled", self.on_toggle, index)
            row.append(check)

            text = item.get("text", "")
            label = Gtk.Label(xalign=0, hexpand=True, wrap=True)
            if item.get("done"):
                label.add_css_class("dim-label")
                label.set_markup(f"<s>{GLib.markup_escape_text(text)}</s>")
            else:
                label.set_label(text)
            row.append(label)

            remove_button = Gtk.Button(icon_name="edit-delete-symbolic", has_frame=False)
            remove_button.set_tooltip_text("Remove")
            remove_button.connect("clicked", lambda _b, i=index: self.on_remove(i))
            row.append(remove_button)

            self.list_box.append(row)
