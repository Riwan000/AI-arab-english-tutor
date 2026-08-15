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


def test_save_session_persists_user_id_on_the_conversation_row(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    user_id = db.create_user("learner@example.com", "hash", "Learner")

    conversation_id = db.save_session(
        lesson={"id": "present_simple", "title": "Present Simple"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
        user_id=user_id,
    )

    conn = db.get_connection()
    row = conn.execute(
        "SELECT user_id FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    conn.close()

    assert row["user_id"] == user_id


def test_save_session_defaults_user_id_to_null(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")

    conversation_id = db.save_session(
        lesson={"id": None, "title": "Free Talk"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
    )

    conn = db.get_connection()
    row = conn.execute(
        "SELECT user_id, lesson_id, lesson_title FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    conn.close()

    assert row["user_id"] is None
    assert row["lesson_id"] is None
    assert row["lesson_title"] == "Free Talk"
