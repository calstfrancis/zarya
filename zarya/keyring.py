import gi

gi.require_version("Secret", "1")

from gi.repository import GLib, Secret

_GOOGLE_SCHEMA = Secret.Schema.new(
    "io.github.calstfrancis.zarya.google_calendar",
    Secret.SchemaFlags.NONE,
    {"account": Secret.SchemaAttributeType.STRING},
)


class KeyringError(Exception):
    """Raised when the system Secret Service (KWallet/gnome-keyring) is
    unreachable — happens if it's not running yet, still locked, or the
    portal hasn't finished activating it. Never let this crash the app."""


def store_google_refresh_token(refresh_token, account="default"):
    try:
        Secret.password_store_sync(
            _GOOGLE_SCHEMA, {"account": account}, Secret.COLLECTION_DEFAULT,
            "Zarya Google Calendar refresh token", refresh_token, None,
        )
    except GLib.Error as e:
        raise KeyringError(str(e)) from e


def lookup_google_refresh_token(account="default"):
    try:
        return Secret.password_lookup_sync(_GOOGLE_SCHEMA, {"account": account}, None)
    except GLib.Error:
        return None


def clear_google_refresh_token(account="default"):
    try:
        Secret.password_clear_sync(_GOOGLE_SCHEMA, {"account": account}, None)
    except GLib.Error:
        pass
