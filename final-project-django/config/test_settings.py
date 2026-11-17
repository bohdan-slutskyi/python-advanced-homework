"""SQLite-only isolated logic tests.

The real schema is accepted on MySQL. This adapter only supplies the
MySQL case-sensitive collation name used by three Choices fields.
"""

from django.db.backends.signals import connection_created

from .settings import *  # noqa: F401, F403


def register_test_collation(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        connection.connection.create_collation(
            "utf8mb4_0900_bin",
            lambda left, right: (left > right) - (left < right),
        )


connection_created.connect(
    register_test_collation, dispatch_uid="housing_sqlite_test_collation"
)
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
