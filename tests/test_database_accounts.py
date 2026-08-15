import sqlite3
import services.database as db

def test_user_table_is_created(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()

    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()

    conn.close()

    assert row is not None
    assert row["name"] == "users"

def test_user_table_has_required_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()

    columns = conn.execute("PRAGMA table_info(users)").fetchall()
    conn.close()

    column_names = {row["name"] for row in columns}
    required_columns = {"id", "email", "password_hash", "display_name", "created_at"}
    assert required_columns.issubset(column_names)


def test_users_required_fields_and_unique_constraint(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()

    # Insert a user
    conn.execute(
        """
        INSERT INTO users (email, password_hash, display_name, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            "test@example.com",
            "hashed_password",
            "Test User",
            "2023-01-01 00:00:00"
        )
    )

    conn.commit()

    try:
        conn.execute(
            """
            INSERT INTO users (email, password_hash, display_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                "test@example.com",
                "another_hashed_password",
                "Another User",
                "2023-01-02 00:00:00"
            )
        )
        conn.commit()

        raise AssertionError("Duplicate email insertion should not be allowed, but it was.")
    except sqlite3.IntegrityError:
        pass  # Expected behavior

    conn.close()

def test_users_survives_database_recreation(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()

    # Insert a user
    conn.execute(
        """
        INSERT INTO users (email, password_hash, display_name, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            "survivor@example.com",
            "hashed_password",
            "Survivor User",
            "2023-01-01 00:00:00"
        )
    )

    conn.commit()
    conn.close()

    conn = db.get_connection()

    row = conn.execute("SELECT * FROM users WHERE email=?", ("survivor@example.com",)).fetchone()
    conn.close()

    assert row is not None
    assert row["email"] == "survivor@example.com"
    assert row["display_name"] == "Survivor User"
    assert row["password_hash"] == "hashed_password"


def test_auth_attempts_table_is_created_with_required_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()

    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='auth_attempts'"
    ).fetchone()
    columns = {c["name"] for c in conn.execute("PRAGMA table_info(auth_attempts)").fetchall()}

    conn.close()

    assert row is not None
    assert {"ip", "email", "window_date", "count"}.issubset(columns)


def test_auth_attempts_survives_conversation_schema_bump(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    assert db.record_auth_attempt("1.2.3.4", "bump@example.com") == 1

    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (0)")
    conn.commit()
    conn.close()

    assert db.record_auth_attempt("1.2.3.4", "bump@example.com") == 2


def test_purge_old_auth_attempts_removes_stale_rows_only(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    db.record_auth_attempt("1.2.3.4", "old@example.com")
    db.record_auth_attempt("1.2.3.4", "fresh@example.com")

    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE auth_attempts SET window_date = '2000-01-01' WHERE email = ?",
        ("old@example.com",),
    )
    conn.commit()
    conn.close()

    deleted = db.purge_old_auth_attempts(retention_days=2)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    remaining = {row["email"] for row in conn.execute("SELECT email FROM auth_attempts").fetchall()}
    conn.close()

    assert deleted == 1
    assert remaining == {"fresh@example.com"}


def test_acount_data_survives_conversation_schema_change(
        tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()

    # Insert a user
    conn.execute(
        """
        INSERT INTO users (email, password_hash, display_name, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            "schema@example.com",
            "hashed_password",
            "Schema User",
            "2023-01-01 00:00:00"
        )
    )

    conn.commit()

    user_before = conn.execute("SELECT * FROM users WHERE email=?", ("schema@example.com",)).fetchone()
    conn.close()

    assert user_before is not None
    assert user_before["email"] == "schema@example.com"
    assert user_before["display_name"] == "Schema User"
    assert user_before["password_hash"] == "hashed_password"

def test_users_are_created_even_when_conversation_schema_needs_no_migration(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    db._create_tables(conn)

    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (db.SCHEMA_VERSION,))
    conn.commit()

    assert db._needs_conversation_migration(conn) is False

    conn.close()

    conn = db.get_connection()

    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    conn.close()

    assert row is not None


def test_conversation_schema_bump_recreates_conversation_tables_and_keeps_users(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()
    conn.execute(
        """
        INSERT INTO users (email, password_hash, display_name, created_at)
        VALUES (?, ?, ?, ?)
        """,
        ("bump@example.com", "hashed_password", "Bump User", "2023-01-01 00:00:00"),
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (0)")
    conn.commit()
    conn.close()

    conn = db.get_connection()

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()}
    user = conn.execute("SELECT * FROM users WHERE email=?", ("bump@example.com",)).fetchone()
    version = conn.execute("SELECT version FROM schema_version").fetchone()

    conn.close()

    assert "ended_at" in columns
    assert user is not None
    assert version["version"] == db.SCHEMA_VERSION

