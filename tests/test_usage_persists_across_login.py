"""The same-day usage counter must survive a logout/login cycle (issue #137).

`daily_usage` is keyed by user_id + date server-side, not carried in the JWT,
so a fresh token from a second `/auth/login` call for the same account must
still see the count run up under the first token.
"""

import os

import pytest
from fastapi.testclient import TestClient

SECRET = "test-only-secret"
os.environ.setdefault("JWT_SECRET_KEY", SECRET)

from api.main import app  # noqa: E402 (secret must be set before import)
from services import openrouter  # noqa: E402

EMAIL = "learner@example.com"
PASSWORD = "correct horse battery staple"


@pytest.fixture
def scoped_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    monkeypatch.setenv("DAILY_MESSAGE_LIMIT", "5")
    monkeypatch.setattr(openrouter, "chat_completion_stream", lambda messages: iter(["ok"]))

    from api.config import get_settings

    get_settings.cache_clear()

    from api.rate_limit import limiter

    monkeypatch.setattr(limiter, "enabled", False)

    yield TestClient(app)

    get_settings.cache_clear()


def _auth_headers(response) -> dict:
    assert response.status_code in (200, 201), response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_usage_counter_survives_a_logout_login_cycle(scoped_client):
    signup_headers = _auth_headers(
        scoped_client.post(
            "/api/v1/auth/signup",
            json={"email": EMAIL, "password": PASSWORD, "display_name": "Learner"},
        )
    )

    scoped_client.post(
        "/api/v1/chat/message",
        headers=signup_headers,
        json={"lesson_id": "present_simple", "messages": [{"role": "user", "content": "hello"}]},
    )
    scoped_client.post(
        "/api/v1/chat/message",
        headers=signup_headers,
        json={"lesson_id": "present_simple", "messages": [{"role": "user", "content": "again"}]},
    )

    # "logout" â€” the client discards its token; "login" â€” a fresh one is issued
    # via the same route the UI calls after a real logout/login cycle.
    login_headers = _auth_headers(
        scoped_client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    )

    response = scoped_client.get("/api/v1/usage/today", headers=login_headers)

    assert response.status_code == 200
    assert response.json()["messages_used"] == 2


def test_messages_sent_after_relogin_add_to_the_same_days_count(scoped_client):
    signup_headers = _auth_headers(
        scoped_client.post(
            "/api/v1/auth/signup",
            json={"email": EMAIL, "password": PASSWORD, "display_name": "Learner"},
        )
    )
    scoped_client.post(
        "/api/v1/chat/message",
        headers=signup_headers,
        json={"lesson_id": "present_simple", "messages": [{"role": "user", "content": "hello"}]},
    )

    login_headers = _auth_headers(
        scoped_client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    )
    scoped_client.post(
        "/api/v1/chat/message",
        headers=login_headers,
        json={"lesson_id": "present_simple", "messages": [{"role": "user", "content": "again"}]},
    )

    response = scoped_client.get("/api/v1/usage/today", headers=login_headers)

    assert response.json()["messages_used"] == 2
