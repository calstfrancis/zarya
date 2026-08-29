from gi.repository import Gio, GLib

# Talks to the StatusNotifierItem/StatusNotifierWatcher protocol directly
# over D-Bus — this is the actual mechanism underneath libappindicator, not
# a re-implementation of it. Avoids needing that library at all (it isn't in
# the org.gnome.Platform runtime and would need its own flatpak module), at
# the cost of a hand-rolled minimal item: icon + click-to-toggle, no
# DBusMenu-based right-click menu. If no StatusNotifierWatcher is running
# (some desktops don't ship one), registration just silently fails and the
# app works exactly as it did without a tray icon — never a hard error.

WATCHER_BUS_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_OBJECT_PATH = "/StatusNotifierWatcher"
ITEM_OBJECT_PATH = "/StatusNotifierItem"

SNI_INTROSPECTION_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <method name="Activate">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="Scroll">
      <arg type="i" name="delta" direction="in"/>
      <arg type="s" name="orientation" direction="in"/>
    </method>
    <signal name="NewIcon"/>
    <signal name="NewStatus">
      <arg type="s" name="status"/>
    </signal>
  </interface>
</node>
"""

_PROPERTY_TYPES = {
    "Category": "s",
    "Id": "s",
    "Title": "s",
    "Status": "s",
    "WindowId": "i",
    "IconName": "s",
    "ItemIsMenu": "b",
}


class TrayIcon:
    def __init__(self, icon_name, on_activate):
        self.icon_name = icon_name
        self.on_activate = on_activate
        self.connection = None
        self.registered = False
        Gio.bus_get(Gio.BusType.SESSION, None, self._on_bus_get)

    def _on_bus_get(self, _source, result):
        try:
            self.connection = Gio.bus_get_finish(result)
            node_info = Gio.DBusNodeInfo.new_for_xml(SNI_INTROSPECTION_XML)
            interface_info = node_info.interfaces[0]
            self.connection.register_object(
                ITEM_OBJECT_PATH, interface_info,
                self._handle_method_call, self._handle_get_property, None,
            )
            self.connection.call(
                WATCHER_BUS_NAME, WATCHER_OBJECT_PATH, WATCHER_BUS_NAME,
                "RegisterStatusNotifierItem", GLib.Variant("(s)", (ITEM_OBJECT_PATH,)),
                None, Gio.DBusCallFlags.NONE, -1, None, self._on_registered,
            )
        except GLib.Error:
            pass

    def _on_registered(self, connection, result):
        try:
            connection.call_finish(result)
            self.registered = True
        except GLib.Error:
            pass

    def _handle_get_property(self, _connection, _sender, _path, _interface, prop_name):
        values = {
            "Category": "ApplicationStatus",
            "Id": "io.github.calstfrancis.zarya",
            "Title": "Zarya",
            "Status": "Active",
            "WindowId": 0,
            "IconName": self.icon_name,
            "ItemIsMenu": False,
        }
        if prop_name not in values:
            return None
        return GLib.Variant(_PROPERTY_TYPES[prop_name], values[prop_name])

    def _handle_method_call(self, _connection, _sender, _path, _interface, method, _params, invocation):
        if method in ("Activate", "SecondaryActivate", "ContextMenu"):
            self.on_activate()
        invocation.return_value(None)
