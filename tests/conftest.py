"""Shared pytest setup: every test runs against an empty Postgres schema.

The suite talks to a real Postgres (the local Supabase CLI stack by default),
so isolation comes from truncating the app tables before each test rather than
from a throwaway database file. `RESTART IDENTITY` resets the identity
sequences so ids start at 1 in every test, and `CASCADE` lets the truncate span
the FK graph (conversations -> messages -> grammar_feedback) in one statement.
"""

import os

import pytest

# Must be set before any test module imports `api.main`, which builds Settings
# at import time and now requires DATABASE_URL.
DEFAULT_TEST_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
os.environ.setdefault("DATABASE_URL", DEFAULT_TEST_DATABASE_URL)

from services import database  # noqa: E402 (env must be set before import)

APP_TABLES = (
    "users",
    "auth_attempts",
    "daily_usage",
    "conversations",
    "messages",
    "grammar_feedback",
)

TRUNCATE_SQL = (
    f"TRUNCATE TABLE {', '.join(APP_TABLES)} RESTART IDENTITY CASCADE"
)


@pytest.fixture(scope="session", autouse=True)
def close_pool_after_session():
    """Shut the pool down cleanly; otherwise its worker threads outlive the
    interpreter and psycopg_pool warns at exit."""
    yield
    database.close_pool()


@pytest.fixture(autouse=True)
def clean_database():
    """Start every test from an empty schema with ids reset to 1."""
    os.environ.setdefault("DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    database.open_pool()  # no-op when the pool is already open

    with database.get_connection() as conn:
        conn.execute(TRUNCATE_SQL)

    yield
