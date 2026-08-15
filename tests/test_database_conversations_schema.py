import sqlite3

import services.database as db


def test_fresh_db_conversations_table_has_new_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()}
    conn.close()

    assert {"user_id", "difficulty", "mode"}.issubset(columns)


def test_fresh_db_lesson_id_and_lesson_title_accept_null(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()
    conn.execute(
        """
        INSERT INTO conversations (lesson_id, lesson_title, mode, created_at, ended_at)
        VALUES (NULL, NULL, 'free_talk', ?, ?)
        """,
        ("2023-01-01 00:00:00", "2023-01-01 00:30:00"),
    )
    conn.commit()

    row = conn.execute("SELECT lesson_id, lesson_title, mode FROM conversations").fetchone()
    conn.close()

    assert row["lesson_id"] is None
    assert row["lesson_title"] is None
    assert row["mode"] == "free_talk"


def test_existing_v2_conversations_gain_new_columns_without_losing_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    # Build a pre-migration (v2-shaped) database directly, bypassing the
    # additive migration, to simulate an existing install upgrading in place.
    # Includes `messages` (FK -> conversations, ON DELETE CASCADE) since the
    # rebuild drops and recreates the `conversations` table by name and must
    # not orphan or break that relationship.
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id TEXT NOT NULL,
            lesson_title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ended_at TEXT NOT NULL,
            grammar_score INTEGER,
            exchange_count INTEGER,
            mistake_count INTEGER,
            vocabulary TEXT,
            recommendation TEXT,
            model_used TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            lesson_id TEXT,
            has_correction INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE TABLE schema_version (version INTEGER NOT NULL);
        INSERT INTO schema_version (version) VALUES (2);
    """)
    conn.execute(
        """
        INSERT INTO conversations (lesson_id, lesson_title, created_at, ended_at, grammar_score)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("present_simple", "Present Simple", "2023-01-01 00:00:00", "2023-01-01 00:30:00", 90),
    )
    conn.execute(
        """
        INSERT INTO messages (conversation_id, role, content, timestamp, sequence)
        VALUES (1, 'user', 'Hi', '2023-01-01 00:00:00', 0)
        """
    )
    conn.commit()
    conn.close()

    conn = db.get_connection()
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()}
    row = conn.execute(
        "SELECT lesson_id, lesson_title, grammar_score, user_id, difficulty, mode FROM conversations"
    ).fetchone()
    message = conn.execute("SELECT conversation_id, content FROM messages").fetchone()

    assert {"user_id", "difficulty", "mode"}.issubset(columns)
    assert row["lesson_id"] == "present_simple"
    assert row["lesson_title"] == "Present Simple"
    assert row["grammar_score"] == 90
    assert row["user_id"] is None
    assert row["difficulty"] is None
    assert row["mode"] == "lesson"
    assert message["conversation_id"] == 1
    assert message["content"] == "Hi"

    # The FK relationship survived the rebuild-by-name: cascade delete still works.
    conn.execute("DELETE FROM conversations WHERE id = 1")
    conn.commit()
    remaining_messages = conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"]
    conn.close()

    assert remaining_messages == 0


def test_migration_cleans_up_staging_table_on_failure(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    # Build a v2-shaped DB, then leave a stray `conversations_v3` table behind
    # so the CREATE TABLE step inside the migration fails partway through.
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id TEXT NOT NULL,
            lesson_title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ended_at TEXT NOT NULL,
            grammar_score INTEGER,
            exchange_count INTEGER,
            mistake_count INTEGER,
            vocabulary TEXT,
            recommendation TEXT,
            model_used TEXT
        );
        CREATE TABLE conversations_v3 (dummy TEXT);
        CREATE TABLE schema_version (version INTEGER NOT NULL);
        INSERT INTO schema_version (version) VALUES (2);
    """)
    conn.commit()
    conn.close()

    try:
        db.get_connection()
        raised = False
    except sqlite3.DatabaseError:
        raised = True

    assert raised, "expected the migration to surface the failure, not swallow it"

    # The stray staging table must be cleaned up — otherwise every subsequent
    # connection attempt fails forever with "table conversations_v3 already
    # exists", since `_migrate_conversations_ownership_and_mode` runs on every
    # connect. Prove that by retrying: it must now succeed (self-heal), not
    # repeat the same failure.
    conn = db.get_connection()
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()}
    conn.close()

    assert {"user_id", "difficulty", "mode"}.issubset(columns)


def test_migration_is_idempotent_across_repeated_connections(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()
    conn.execute(
        """
        INSERT INTO conversations (lesson_id, lesson_title, mode, created_at, ended_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("present_simple", "Present Simple", "lesson", "2023-01-01 00:00:00", "2023-01-01 00:30:00"),
    )
    conn.commit()
    conn.close()

    # A second connection should find the migration already applied (no-op)
    # and must not disturb the row inserted above.
    conn = db.get_connection()
    count = conn.execute("SELECT COUNT(*) AS n FROM conversations").fetchone()["n"]
    conn.close()

    assert count == 1
