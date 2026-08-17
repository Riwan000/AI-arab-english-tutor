"""Tests for draft (in-progress) conversation persistence."""

from repositories.draft_repo import DraftRepository
from services import database as db


def _messages() -> list[dict]:
    return [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hello! How are you?"},
    ]


# --- services.database: save_draft / get_draft / delete_draft ------------------


def test_database_draft_table_is_created_with_required_columns():
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'draft_conversations'
            """
        ).fetchone()
        columns = {
            c["column_name"]
            for c in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'draft_conversations'
                """
            ).fetchall()
        }

    assert row is not None
    assert {
        "id", "user_id", "lesson_id", "mode", "difficulty", "messages", "updated_at",
    }.issubset(columns)


def test_get_draft_returns_none_when_no_draft_exists():
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    assert db.get_draft(user_id) is None


def test_save_draft_then_get_draft_round_trips_messages():
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    db.save_draft(user_id, messages=_messages(), lesson_id=None, mode="free_talk", difficulty="beginner")
    draft = db.get_draft(user_id)

    assert draft is not None
    assert draft["messages"] == _messages()
    assert draft["mode"] == "free_talk"
    assert draft["difficulty"] == "beginner"


def test_save_draft_upserts_a_single_row_per_user():
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    db.save_draft(user_id, messages=_messages(), mode="free_talk")
    db.save_draft(user_id, messages=[{"role": "user", "content": "second draft"}], mode="free_talk")

    draft = db.get_draft(user_id)
    assert draft["messages"] == [{"role": "user", "content": "second draft"}]

    with db.get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM draft_conversations WHERE user_id = %s", (user_id,)
        ).fetchone()["n"]
    assert count == 1


def test_delete_draft_removes_the_row():
    user_id = db.create_user("learner@example.com", "hash", "Learner")
    db.save_draft(user_id, messages=_messages(), mode="free_talk")

    db.delete_draft(user_id)

    assert db.get_draft(user_id) is None


def test_delete_draft_is_idempotent_when_no_draft_exists():
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    db.delete_draft(user_id)  # must not raise


def test_draft_is_scoped_per_user():
    owner = db.create_user("owner@example.com", "hash", "Owner")
    other = db.create_user("other@example.com", "hash", "Other")

    db.save_draft(owner, messages=_messages(), mode="free_talk")

    assert db.get_draft(other) is None
    assert db.get_draft(owner) is not None


# --- repositories.draft_repo.DraftRepository ------------------------------------


def test_repository_save_get_delete_round_trip():
    user_id = db.create_user("learner@example.com", "hash", "Learner")
    repo = DraftRepository()

    repo.save(user_id, messages=_messages(), mode="free_talk")
    assert repo.get(user_id)["messages"] == _messages()

    repo.delete(user_id)
    assert repo.get(user_id) is None
