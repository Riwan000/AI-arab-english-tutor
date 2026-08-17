"""Phase 7 exit verification â€” issues #135-#138.

HTTP-level regression coverage on top of the existing service/repository unit
tests (test_usage_service.py, test_usage_repository.py,
test_route_chat_usage_limit.py): these exercise the real FastAPI routes and
the real `api_client` error-handling path end to end, so a regression at the
request layer or in the frontend's 429 handling would be caught even if the
lower-level unit tests still pass.
"""

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

SECRET = "test-only-secret"
os.environ.setdefault("JWT_SECRET_KEY", SECRET)

import api_client  # noqa: E402
from api.main import app  # noqa: E402 (secret must be set before import)
from services import openrouter  # noqa: E402

CHAT_URL = "http://localhost:8000/api/v1/chat/message"


@pytest.fixture
def scoped_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    monkeypatch.setenv("DAILY_MESSAGE_LIMIT", "2")
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: "Great job!")

    from api.config import get_settings

    get_settings.cache_clear()

    from api.rate_limit import limiter

    monkeypatch.setattr(limiter, "enabled", False)

    yield TestClient(app)

    get_settings.cache_clear()


@pytest.fixture
def fake_st():
    """A stand-in for streamlit with a real dict session_state, so writes are assertable."""
    st = MagicMock()
    st.session_state = {}
    with patch.object(api_client, "st", st):
        yield st


def _signup(scoped_client, email: str) -> dict:
    response = scoped_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct horse battery staple", "display_name": "Learner"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _send(scoped_client, headers, text: str):
    return scoped_client.post(
        "/api/v1/chat/message",
        headers=headers,
        json={"lesson_id": "present_simple", "messages": [{"role": "user", "content": text}]},
    )


# --- #136: looping messages past DAILY_MESSAGE_LIMIT mid-conversation returns 429 -------


def test_message_past_the_limit_mid_conversation_returns_429_with_correct_remaining_count(
    scoped_client,
):
    headers = _signup(scoped_client, "phase7-136@example.com")

    first = _send(scoped_client, headers, "hi")
    second = _send(scoped_client, headers, "how are you")
    third = _send(scoped_client, headers, "one more, past the limit")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert third.status_code == 429, third.text
    body = third.json()["detail"]
    assert body["remaining"] == 0
    assert body["message"]  # Arabic-first message, non-empty


# --- #135: that same 429 body, fed through the real frontend error path, blocks input ---


def test_hitting_the_limit_mid_conversation_blocks_the_frontend_gracefully(
    scoped_client, fake_st
):
    headers = _signup(scoped_client, "phase7-135@example.com")
    _send(scoped_client, headers, "hi")
    _send(scoped_client, headers, "how are you")
    blocked = _send(scoped_client, headers, "should be blocked")
    assert blocked.status_code == 429, blocked.text

    # Replay the real backend response through api_client's real error path â€”
    # the same path a live Streamlit session hits when send_message() 429s.
    request = httpx.Request("POST", CHAT_URL)
    response = httpx.Response(429, json=blocked.json(), request=request)
    exc = httpx.HTTPStatusError("429", request=request, response=response)

    api_client._handle_response_error(exc)

    assert fake_st.session_state["daily_limit_reached"] is True
    fake_st.error.assert_called_once_with(blocked.json()["detail"]["message"])


# --- #137: usage counter persists across a logout/login cycle --------------------------


def test_usage_counter_persists_across_login_logout_mid_phase(scoped_client):
    email, password = "phase7-137@example.com", "correct horse battery staple"
    signup_headers = _signup(scoped_client, email)
    _send(scoped_client, signup_headers, "hi")

    login = scoped_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    login_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    usage = scoped_client.get("/api/v1/usage/today", headers=login_headers)
    assert usage.status_code == 200, usage.text
    assert usage.json()["messages_used"] == 1
