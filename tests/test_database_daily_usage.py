import psycopg
import pytest

import services.database as db


def test_daily_usage_table_is_created_with_required_columns():
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'daily_usage'
            """
        ).fetchone()
        columns = {
            c["column_name"]
            for c in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'daily_usage'
                """
            ).fetchall()
        }

    assert row is not None
    assert {
        "id", "user_id", "usage_date", "message_count", "voice_call_count", "updated_at",
    }.issubset(columns)


def test_daily_usage_enforces_one_row_per_user_per_day():
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_usage (user_id, usage_date, message_count, voice_call_count, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (1, "2026-08-16", 1, 0, "2026-08-16T00:00:00+00:00"),
        )

    with pytest.raises(psycopg.errors.UniqueViolation):
        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO daily_usage (user_id, usage_date, message_count, voice_call_count, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (1, "2026-08-16", 1, 0, "2026-08-16T00:00:01+00:00"),
            )


# --- increment_daily_message_count / increment_daily_voice_call_count ---------


def test_increment_daily_message_count_starts_a_new_row_at_one():
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    count = db.increment_daily_message_count(user_id)

    assert count == 1


def test_increment_daily_message_count_increments_an_existing_row():
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    db.increment_daily_message_count(user_id)
    db.increment_daily_message_count(user_id)
    count = db.increment_daily_message_count(user_id)

    assert count == 3


def test_increment_daily_voice_call_count_starts_a_new_row_at_one():
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    count = db.increment_daily_voice_call_count(user_id)

    assert count == 1


def test_message_and_voice_counters_are_independent_on_the_same_row():
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    db.increment_daily_message_count(user_id)
    db.increment_daily_message_count(user_id)
    db.increment_daily_voice_call_count(user_id)

    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT message_count, voice_call_count FROM daily_usage WHERE user_id = %s",
            (user_id,),
        ).fetchone()

    assert row["message_count"] == 2
    assert row["voice_call_count"] == 1


def test_increment_daily_message_count_is_scoped_per_user():
    user_a = db.create_user("a@example.com", "hash", "A")
    user_b = db.create_user("b@example.com", "hash", "B")

    db.increment_daily_message_count(user_a)

    assert db.increment_daily_message_count(user_b) == 1


# --- get_daily_usage ------------------------------------------------------------


def test_get_daily_usage_returns_zeros_when_no_activity_yet():
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    usage = db.get_daily_usage(user_id)

    assert usage == {"message_count": 0, "voice_call_count": 0}


def test_get_daily_usage_reflects_recorded_activity():
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    db.increment_daily_message_count(user_id)
    db.increment_daily_message_count(user_id)
    db.increment_daily_voice_call_count(user_id)

    usage = db.get_daily_usage(user_id)

    assert usage == {"message_count": 2, "voice_call_count": 1}


def test_get_daily_usage_is_scoped_per_user():
    user_a = db.create_user("a@example.com", "hash", "A")
    user_b = db.create_user("b@example.com", "hash", "B")

    db.increment_daily_message_count(user_a)

    assert db.get_daily_usage(user_b) == {"message_count": 0, "voice_call_count": 0}
