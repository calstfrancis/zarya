import gi

gi.require_version("Secret", "1")

from gi.repository import Secret

_GOOGLE_SCHEMA = Secret.Schema.new(
    "io.github.calstfrancis.zarya.google_calendar",
    Secret.SchemaFlags.NONE,
    {"account": Secret.SchemaAttributeType.STRING},
)


def store_google_refresh_token(refresh_token, account="default"):
    Secret.password_store_sync(
        _GOOGLE_SCHEMA, {"account": account}, Secret.COLLECTION_DEFAULT,
        "Zarya Google Calendar refresh token", refresh_token, None,
    )


def lookup_google_refresh_token(account="default"):
    return Secret.password_lookup_sync(_GOOGLE_SCHEMA, {"account": account}, None)


def clear_google_refresh_token(account="default"):
    Secret.password_clear_sync(_GOOGLE_SCHEMA, {"account": account}, None)
