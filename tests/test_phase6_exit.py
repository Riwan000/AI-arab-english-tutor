"""Phase 6 exit verification â€” issues #121-#124.

HTTP-level regression coverage on top of the existing service/repository unit
tests: these exercise the real FastAPI routes so a regression at the request
layer (schema defaults, dependency wiring) would be caught even if the
service-layer tests still pass.
"""

import os

import pytest
from fastapi.testclient import TestClient

SECRET = "test-only-secret"
os.environ.setdefault("JWT_SECRET_KEY", SECRET)

from api.main import app  # noqa: E402 (secret must be set before import)
from services import conversation  # noqa: E402


@pytest.fixture
def scoped_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)

    from api.config import get_settings

    get_settings.cache_clear()

    from api.rate_limit import limiter

    monkeypatch.setattr(limiter, "enabled", False)

    # Deliberately not a context manager: running the lifespan would re-read
    # settings and re-open the connection pool the conftest fixture manages.
    yield TestClient(app)

    get_settings.cache_clear()


def _signup(scoped_client, email: str) -> dict:
    response = scoped_client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": "Test User",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _fail_get_lesson(lesson_id):
    raise AssertionError("lessons.get_lesson should not be called in free_talk mode")


# --- #121: Free Talk starts without a lesson_id -------------------------------


def test_start_chat_free_talk_without_lesson_id_succeeds(scoped_client, monkeypatch):
    monkeypatch.setattr(conversation.lessons, "get_lesson", _fail_get_lesson)
    monkeypatch.setattr(conversation.openrouter, "chat_completion", lambda messages: "Hi there!")
    headers = _signup(scoped_client, "free-talk-start@example.com")

    response = scoped_client.post(
        "/api/v1/chat/start",
        headers=headers,
        json={"mode": "free_talk"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["reply"] == "Hi there!"


def test_send_chat_message_free_talk_without_lesson_id_succeeds(scoped_client, monkeypatch):
    monkeypatch.setattr(conversation.lessons, "get_lesson", _fail_get_lesson)
    monkeypatch.setattr(conversation.openrouter, "chat_completion", lambda messages: "Great job!")
    headers = _signup(scoped_client, "free-talk-message@example.com")

    response = scoped_client.post(
        "/api/v1/chat/message",
        headers=headers,
        json={"mode": "free_talk", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["reply"] == "Great job!"


# --- #122: lesson-constrained flow is unaffected -------------------------------


def test_start_chat_lesson_mode_still_resolves_lesson_by_default(scoped_client, monkeypatch):
    """Omitting `mode` entirely must still behave like lesson mode did before Phase 6."""
    captured = {}

    def fake_completion(messages):
        captured["messages"] = messages
        return "Let's practice the present simple."

    monkeypatch.setattr(conversation.openrouter, "chat_completion", fake_completion)
    headers = _signup(scoped_client, "lesson-start@example.com")

    response = scoped_client.post(
        "/api/v1/chat/start",
        headers=headers,
        json={"lesson_id": "present_simple"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["reply"] == "Let's practice the present simple."
    # A real lesson prompt was built (not the Free-Talk/no-lesson path).
    assert "messages" in captured


def test_create_session_lesson_mode_still_stores_lesson_fields(scoped_client):
    headers = _signup(scoped_client, "lesson-save@example.com")

    response = scoped_client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "lesson_id": "present_simple",
            "messages": [{"role": "user", "content": "I go to school yesterday."}],
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    session_id = body["id"]

    detail = scoped_client.get(f"/api/v1/sessions/{session_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["lesson_id"] == "present_simple"
    assert detail.json()["lesson_title"] == "Present Simple"


# --- #124: mode/difficulty picker -> Free Talk -> save -> summary, end to end -


def test_free_talk_journey_from_start_to_saved_summary(scoped_client, monkeypatch):
    monkeypatch.setattr(conversation.lessons, "get_lesson", _fail_get_lesson)

    def fake_completion(messages):
        return (
            "Great effort!\n"
            "```json\n"
            '{"corrections": [{"mistake_type": "verb_tense", '
            '"wrong_text": "I go", "correct_text": "I went", '
            '"english_explanation": "Use past tense for a completed action.", '
            '"arabic_explanation": "Ø§Ø³ØªØ®Ø¯Ù… Ø§Ù„Ù…Ø§Ø¶ÙŠ Ù„Ù„ÙØ¹Ù„ Ø§Ù„Ù…ÙƒØªÙ…Ù„."}]}\n'
            "```"
        )

    monkeypatch.setattr(conversation.openrouter, "chat_completion", fake_completion)
    headers = _signup(scoped_client, "phase6-journey@example.com")

    # 1. picker: mode=free_talk, difficulty=advanced, no lesson.
    start = scoped_client.post(
        "/api/v1/chat/start",
        headers=headers,
        json={"mode": "free_talk", "difficulty": "advanced"},
    )
    assert start.status_code == 200, start.text

    # 2. one turn of Free Talk conversation with a deliberate grammar mistake.
    message = scoped_client.post(
        "/api/v1/chat/message",
        headers=headers,
        json={
            "mode": "free_talk",
            "difficulty": "advanced",
            "messages": [{"role": "user", "content": "I go to the market yesterday."}],
        },
    )
    assert message.status_code == 200, message.text
    corrections = message.json()["corrections"]
    assert len(corrections) == 1
    assert corrections[0]["mistake_type"] == "verb_tense"

    # 3. end session: save transcript + mistakes.
    save = scoped_client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "mode": "free_talk",
            "messages": [
                {"role": "user", "content": "I go to the market yesterday."},
                {"role": "assistant", "content": message.json()["reply"]},
            ],
            "mistakes": corrections,
        },
    )
    assert save.status_code == 201, save.text
    session_id = save.json()["id"]
    assert save.json()["mistake_count"] == 1

    # 4. summary: shows up in the list and the detail view, scoped to this user.
    listing = scoped_client.get("/api/v1/sessions", headers=headers)
    assert session_id in [item["id"] for item in listing.json()["sessions"]]

    detail = scoped_client.get(f"/api/v1/sessions/{session_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()
    assert detail_body["lesson_id"] is None
    assert detail_body["lesson_title"] == "Free Talk"
    assert detail_body["mistake_count"] == 1
