import sqlite3

import services.database as db


def test_daily_usage_table_is_created_with_required_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()

    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_usage'"
    ).fetchone()
    columns = {c["name"] for c in conn.execute("PRAGMA table_info(daily_usage)").fetchall()}

    conn.close()

    assert row is not None
    assert {
        "id", "user_id", "usage_date", "message_count", "voice_call_count", "updated_at",
    }.issubset(columns)


def test_daily_usage_enforces_one_row_per_user_per_day(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()
    conn.execute(
        """
        INSERT INTO daily_usage (user_id, usage_date, message_count, voice_call_count, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (1, "2026-08-16", 1, 0, "2026-08-16T00:00:00+00:00"),
    )
    conn.commit()

    try:
        conn.execute(
            """
            INSERT INTO daily_usage (user_id, usage_date, message_count, voice_call_count, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (1, "2026-08-16", 1, 0, "2026-08-16T00:00:01+00:00"),
        )
        conn.commit()
        raise AssertionError("Duplicate (user_id, usage_date) should not be allowed, but it was.")
    except sqlite3.IntegrityError:
        pass  # Expected behavior

    conn.close()


def test_daily_usage_survives_conversation_schema_bump(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(db, "DB_PATH", db_path)

    conn = db.get_connection()
    conn.execute(
        """
        INSERT INTO daily_usage (user_id, usage_date, message_count, voice_call_count, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (1, "2026-08-16", 5, 2, "2026-08-16T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    # Simulate an unrelated future conversation-schema bump.
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (0)")
    conn.commit()
    conn.close()

    conn = db.get_connection()
    row = conn.execute(
        "SELECT message_count, voice_call_count FROM daily_usage WHERE user_id = ? AND usage_date = ?",
        (1, "2026-08-16"),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["message_count"] == 5
    assert row["voice_call_count"] == 2


# --- increment_daily_message_count / increment_daily_voice_call_count ---------


def test_increment_daily_message_count_starts_a_new_row_at_one(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    count = db.increment_daily_message_count(user_id)

    assert count == 1


def test_increment_daily_message_count_increments_an_existing_row(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    db.increment_daily_message_count(user_id)
    db.increment_daily_message_count(user_id)
    count = db.increment_daily_message_count(user_id)

    assert count == 3


def test_increment_daily_voice_call_count_starts_a_new_row_at_one(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    count = db.increment_daily_voice_call_count(user_id)

    assert count == 1


def test_message_and_voice_counters_are_independent_on_the_same_row(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    db.increment_daily_message_count(user_id)
    db.increment_daily_message_count(user_id)
    db.increment_daily_voice_call_count(user_id)

    conn = db.get_connection()
    row = conn.execute(
        "SELECT message_count, voice_call_count FROM daily_usage WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()

    assert row["message_count"] == 2
    assert row["voice_call_count"] == 1


def test_increment_daily_message_count_is_scoped_per_user(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    user_a = db.create_user("a@example.com", "hash", "A")
    user_b = db.create_user("b@example.com", "hash", "B")

    db.increment_daily_message_count(user_a)

    assert db.increment_daily_message_count(user_b) == 1
