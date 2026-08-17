"""GET /api/v1/chat/draft must return the caller's own in-progress conversation."""

import os

import pytest
from fastapi.testclient import TestClient

SECRET = "test-only-secret"
os.environ.setdefault("JWT_SECRET_KEY", SECRET)

from api.main import app  # noqa: E402 (secret must be set before import)
from services import database as db  # noqa: E402
from services import openrouter  # noqa: E402


@pytest.fixture
def scoped_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: "ok")

    from api.config import get_settings

    get_settings.cache_clear()

    from api.rate_limit import limiter

    monkeypatch.setattr(limiter, "enabled", False)

    yield TestClient(app)

    get_settings.cache_clear()


def _signup(scoped_client, email: str) -> tuple[dict, int]:
    response = scoped_client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": "Learner",
        },
    )
    assert response.status_code == 201
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


def test_get_draft_returns_null_when_no_draft_exists(scoped_client):
    headers, _ = _signup(scoped_client, "learner@example.com")

    response = scoped_client.get("/api/v1/chat/draft", headers=headers)

    assert response.status_code == 200
    assert response.json() is None


def test_get_draft_returns_the_callers_saved_draft(scoped_client):
    headers, user_id = _signup(scoped_client, "learner@example.com")
    db.save_draft(
        user_id,
        messages=[{"role": "user", "content": "hi"}],
        mode="free_talk",
        difficulty="beginner",
    )

    response = scoped_client.get("/api/v1/chat/draft", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["mode"] == "free_talk"
    assert body["difficulty"] == "beginner"


def test_get_draft_is_scoped_per_user(scoped_client):
    owner_headers, owner_id = _signup(scoped_client, "owner@example.com")
    intruder_headers, _ = _signup(scoped_client, "intruder@example.com")
    db.save_draft(owner_id, messages=[{"role": "user", "content": "hi"}], mode="free_talk")

    intruder_view = scoped_client.get("/api/v1/chat/draft", headers=intruder_headers)

    assert intruder_view.json() is None


def test_sending_a_free_talk_message_creates_a_resumable_draft(scoped_client):
    headers, user_id = _signup(scoped_client, "learner@example.com")

    scoped_client.post(
        "/api/v1/chat/message",
        headers=headers,
        json={"mode": "free_talk", "messages": [{"role": "user", "content": "hello"}]},
    )

    draft = db.get_draft(user_id)
    assert draft is not None
    assert draft["messages"][-1] == {"role": "assistant", "content": "ok"}
