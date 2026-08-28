import gi

gi.require_version("Secret", "1")

from gi.repository import Secret

_SCHEMA = Secret.Schema.new(
    "io.github.calstfrancis.zarya.caldav",
    Secret.SchemaFlags.NONE,
    {
        "server": Secret.SchemaAttributeType.STRING,
        "username": Secret.SchemaAttributeType.STRING,
    },
)


def store_password(server, username, password):
    attributes = {"server": server, "username": username}
    Secret.password_store_sync(
        _SCHEMA, attributes, Secret.COLLECTION_DEFAULT,
        f"Zarya CalDAV password ({username}@{server})",
        password, None,
    )


def lookup_password(server, username):
    attributes = {"server": server, "username": username}
    return Secret.password_lookup_sync(_SCHEMA, attributes, None)
