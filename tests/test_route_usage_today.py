"""GET /api/v1/usage/today must reflect real per-user daily usage server-side."""

import os

import pytest
from fastapi.testclient import TestClient

SECRET = "test-only-secret"
os.environ.setdefault("JWT_SECRET_KEY", SECRET)

from api.main import app  # noqa: E402 (secret must be set before import)
from services import database as db  # noqa: E402
from services import openrouter  # noqa: E402


@pytest.fixture
def scoped_client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "usage.db")
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    monkeypatch.setenv("DAILY_MESSAGE_LIMIT", "5")
    monkeypatch.setenv("DAILY_VOICE_CALL_LIMIT", "3")
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: "ok")

    from api.config import get_settings

    get_settings.cache_clear()

    from api.rate_limit import limiter

    monkeypatch.setattr(limiter, "enabled", False)

    yield TestClient(app)

    get_settings.cache_clear()


def _signup(scoped_client, email: str = "learner@example.com") -> dict:
    response = scoped_client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": "Learner",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_usage_today_requires_authentication(scoped_client):
    response = scoped_client.get("/api/v1/usage/today")

    assert response.status_code == 401


def test_usage_today_returns_full_limits_with_no_activity(scoped_client):
    headers = _signup(scoped_client)

    response = scoped_client.get("/api/v1/usage/today", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["messages_used"] == 0
    assert body["messages_limit"] == 5
    assert body["voice_used"] == 0
    assert body["voice_limit"] == 3


def test_usage_today_reflects_sent_messages(scoped_client):
    headers = _signup(scoped_client)

    scoped_client.post(
        "/api/v1/chat/message",
        headers=headers,
        json={
            "lesson_id": "present_simple",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    response = scoped_client.get("/api/v1/usage/today", headers=headers)

    body = response.json()
    assert body["messages_used"] == 1
    assert body["messages_limit"] == 5


def test_usage_today_is_scoped_per_user(scoped_client):
    owner_headers = _signup(scoped_client, "owner@example.com")
    other_headers = _signup(scoped_client, "other@example.com")

    scoped_client.post(
        "/api/v1/chat/message",
        headers=owner_headers,
        json={
            "lesson_id": "present_simple",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    response = scoped_client.get("/api/v1/usage/today", headers=other_headers)

    assert response.json()["messages_used"] == 0
