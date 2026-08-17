import pytest

from repositories.session_repo import SessionRepository
from services import database as db


def test_save_forwards_user_id_to_database_layer(monkeypatch):
    captured = {}

    def fake_save_session(**kwargs):
        captured.update(kwargs)
        return 7

    monkeypatch.setattr(db, "save_session", fake_save_session)

    conversation_id = SessionRepository().save(
        lesson={"id": "present_simple", "title": "Present Simple"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
        user_id=5,
    )

    assert conversation_id == 7
    assert captured["user_id"] == 5


def test_save_defaults_user_id_to_none(monkeypatch):
    captured = {}

    def fake_save_session(**kwargs):
        captured.update(kwargs)
        return 7

    monkeypatch.setattr(db, "save_session", fake_save_session)

    SessionRepository().save(
        lesson={"id": "present_simple", "title": "Present Simple"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
    )

    assert captured["user_id"] is None


def test_save_session_persists_user_id_on_the_conversation_row():
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    conversation_id = db.save_session(
        lesson={"id": "present_simple", "title": "Present Simple"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
        user_id=user_id,
    )

    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT user_id FROM conversations WHERE id = %s", (conversation_id,)
        ).fetchone()

    assert row["user_id"] == user_id


def test_save_session_defaults_user_id_to_null():
    conversation_id = db.save_session(
        lesson={"id": None, "title": "Free Talk"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
    )

    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT user_id, lesson_id, lesson_title FROM conversations WHERE id = %s",
            (conversation_id,),
        ).fetchone()

    assert row["user_id"] is None
    assert row["lesson_id"] is None
    assert row["lesson_title"] == "Free Talk"


def test_save_forwards_mode_to_database_layer(monkeypatch):
    captured = {}

    def fake_save_session(**kwargs):
        captured.update(kwargs)
        return 7

    monkeypatch.setattr(db, "save_session", fake_save_session)

    SessionRepository().save(
        lesson={"id": None, "title": "Free Talk"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
        mode="free_talk",
    )

    assert captured["mode"] == "free_talk"


def test_save_session_persists_mode_on_the_conversation_row():
    conversation_id = db.save_session(
        lesson={"id": None, "title": "Free Talk"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
        mode="free_talk",
    )

    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT mode FROM conversations WHERE id = %s", (conversation_id,)
        ).fetchone()

    assert row["mode"] == "free_talk"


def test_save_session_defaults_mode_to_lesson():
    conversation_id = db.save_session(
        lesson={"id": "present_simple", "title": "Present Simple"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
    )

    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT mode FROM conversations WHERE id = %s", (conversation_id,)
        ).fetchone()

    assert row["mode"] == "lesson"


# --- ownership filtering on the read paths (IDOR regression, issue #117) ------


def _save_session_for(user_id: int | None) -> int:
    return db.save_session(
        lesson={"id": "present_simple", "title": "Present Simple"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
        user_id=user_id,
    )


@pytest.fixture
def two_users():
    """Owner and intruder ids in the (per-test truncated) database, plus a repository."""
    owner = db.create_user("owner@example.com", "hash", "Owner")
    intruder = db.create_user("intruder@example.com", "hash", "Intruder")
    return SessionRepository(), owner, intruder


def test_list_recent_returns_only_the_callers_own_sessions(two_users):
    repo, owner, intruder = two_users
    session_id = _save_session_for(owner)

    assert [row["id"] for row in repo.list_recent(user_id=owner)] == [session_id]
    assert repo.list_recent(user_id=intruder) == []


def test_list_recent_omits_sessions_with_no_owner(two_users):
    repo, owner, _ = two_users
    _save_session_for(None)

    assert repo.list_recent(user_id=owner) == []


def test_get_summary_returns_the_session_for_its_owner(two_users):
    repo, owner, _ = two_users
    session_id = _save_session_for(owner)

    assert repo.get_summary(session_id, user_id=owner)["id"] == session_id


def test_get_summary_returns_none_for_another_users_session(two_users):
    repo, owner, intruder = two_users
    session_id = _save_session_for(owner)

    assert repo.get_summary(session_id, user_id=intruder) is None


def test_get_summary_treats_a_foreign_session_like_a_missing_one(two_users):
    """Both must be indistinguishable, or ids of other users' sessions leak."""
    repo, owner, intruder = two_users
    session_id = _save_session_for(owner)

    assert repo.get_summary(session_id, user_id=intruder) == repo.get_summary(
        999999, user_id=intruder
    )


def test_get_summary_returns_none_for_a_session_with_no_owner(two_users):
    repo, owner, _ = two_users
    session_id = _save_session_for(None)

    assert repo.get_summary(session_id, user_id=owner) is None
