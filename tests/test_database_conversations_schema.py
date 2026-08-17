"""Schema guarantees the conversation data-access code depends on.

The schema itself is owned by the versioned migrations in
`supabase/migrations/`; these tests assert the shape the app relies on is
actually present in the database the suite runs against.
"""

import services.database as db


def test_conversations_table_has_ownership_and_mode_columns():
    with db.get_connection() as conn:
        columns = {
            row["column_name"]
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'conversations'
                """
            ).fetchall()
        }

    assert {"user_id", "difficulty", "mode"}.issubset(columns)


def test_lesson_id_and_lesson_title_accept_null():
    """Free Talk sessions have no lesson, so both columns must stay nullable."""
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO conversations (lesson_id, lesson_title, mode, created_at, ended_at)
            VALUES (NULL, NULL, 'free_talk', %s, %s)
            """,
            ("2023-01-01 00:00:00+00", "2023-01-01 00:30:00+00"),
        )

        row = conn.execute(
            "SELECT lesson_id, lesson_title, mode FROM conversations"
        ).fetchone()

    assert row["lesson_id"] is None
    assert row["lesson_title"] is None
    assert row["mode"] == "free_talk"
