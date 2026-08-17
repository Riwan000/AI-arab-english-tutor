"""Account-storage guarantees: table shape, constraints and auth-attempt purging.

The schema is owned by the versioned migrations in `supabase/migrations/`;
these tests assert the shape and the constraints the app depends on are
actually present, plus the app-level purge behaviour.
"""

import psycopg
import pytest

import services.database as db


def _columns_of(conn, table: str) -> set[str]:
    return {
        row["column_name"]
        for row in conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        ).fetchall()
    }


def test_users_table_exists():
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'users'
            """
        ).fetchone()

    assert row is not None
    assert row["table_name"] == "users"


def test_user_table_has_required_columns():
    with db.get_connection() as conn:
        column_names = _columns_of(conn, "users")

    required_columns = {"id", "email", "password_hash", "display_name", "created_at"}
    assert required_columns.issubset(column_names)


def test_users_required_fields_and_unique_constraint():
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (email, password_hash, display_name, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            ("test@example.com", "hashed_password", "Test User", "2023-01-01 00:00:00+00"),
        )

    with pytest.raises(psycopg.errors.UniqueViolation):
        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (email, password_hash, display_name, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    "test@example.com",
                    "another_hashed_password",
                    "Another User",
                    "2023-01-02 00:00:00+00",
                ),
            )


def test_users_email_uniqueness_is_case_insensitive():
    """`email` is citext, so the UNIQUE constraint enforces case-insensitivity
    in the database too — not only via the app's manual lowercasing."""
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (email, password_hash, display_name, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            ("case@example.com", "hashed_password", "Case User", "2023-01-01 00:00:00+00"),
        )

    with pytest.raises(psycopg.errors.UniqueViolation):
        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (email, password_hash, display_name, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                ("CASE@Example.com", "hashed_password", "Other", "2023-01-02 00:00:00+00"),
            )


def test_auth_attempts_table_is_created_with_required_columns():
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'auth_attempts'
            """
        ).fetchone()
        columns = _columns_of(conn, "auth_attempts")

    assert row is not None
    assert {"ip", "email", "window_date", "count"}.issubset(columns)


def test_purge_old_auth_attempts_removes_stale_rows_only():
    db.record_auth_attempt("1.2.3.4", "old@example.com")
    db.record_auth_attempt("1.2.3.4", "fresh@example.com")

    with db.get_connection() as conn:
        conn.execute(
            "UPDATE auth_attempts SET window_date = '2000-01-01' WHERE email = %s",
            ("old@example.com",),
        )

    deleted = db.purge_old_auth_attempts(retention_days=2)

    with db.get_connection() as conn:
        remaining = {
            row["email"]
            for row in conn.execute("SELECT email FROM auth_attempts").fetchall()
        }

    assert deleted == 1
    assert remaining == {"fresh@example.com"}
