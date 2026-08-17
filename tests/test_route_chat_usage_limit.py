"""The daily message limit must be enforced on chat.py's LLM-calling routes."""

import os

import pytest
from fastapi.testclient import TestClient

SECRET = "test-only-secret"
os.environ.setdefault("JWT_SECRET_KEY", SECRET)

from api.main import app  # noqa: E402 (secret must be set before import)
from services import openrouter  # noqa: E402


@pytest.fixture
def scoped_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    monkeypatch.setenv("DAILY_MESSAGE_LIMIT", "2")
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


def _send_message(scoped_client, headers):
    return scoped_client.post(
        "/api/v1/chat/message",
        headers=headers,
        json={
            "lesson_id": "present_simple",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )


def test_messages_under_the_daily_limit_succeed(scoped_client):
    headers = _signup(scoped_client)

    first = _send_message(scoped_client, headers)
    second = _send_message(scoped_client, headers)

    assert first.status_code == 200
    assert second.status_code == 200


def test_message_past_the_daily_limit_returns_429_with_remaining_count(scoped_client):
    headers = _signup(scoped_client)

    _send_message(scoped_client, headers)
    _send_message(scoped_client, headers)
    third = _send_message(scoped_client, headers)

    assert third.status_code == 429
    body = third.json()["detail"]
    assert body["remaining"] == 0
    assert body["message"]


def test_usage_limit_is_scoped_per_user(scoped_client):
    owner_headers = _signup(scoped_client, "owner@example.com")
    other_headers = _signup(scoped_client, "other@example.com")

    _send_message(scoped_client, owner_headers)
    _send_message(scoped_client, owner_headers)

    still_under_own_limit = _send_message(scoped_client, other_headers)

    assert still_under_own_limit.status_code == 200


def test_start_chat_also_counts_against_the_daily_limit(scoped_client):
    headers = _signup(scoped_client)

    scoped_client.post(
        "/api/v1/chat/start", headers=headers, json={"lesson_id": "present_simple"}
    )
    scoped_client.post(
        "/api/v1/chat/start", headers=headers, json={"lesson_id": "present_simple"}
    )
    third = scoped_client.post(
        "/api/v1/chat/start", headers=headers, json={"lesson_id": "present_simple"}
    )

    assert third.status_code == 429
