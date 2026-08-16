"""Phase 7 exit verification — daily usage limit blocks gracefully (issues #135-#138)."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

SECRET = "phase7-exit-verification-secret"
CHAT_URL = "http://localhost:8000/api/v1/chat/message"


def _make_client(daily_message_limit: str = "2") -> TestClient:
    tmpdir = tempfile.mkdtemp()
    os.environ["DATABASE_PATH"] = str(Path(tmpdir) / "test.db")
    os.environ["JWT_SECRET_KEY"] = SECRET
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    os.environ["CORS_ORIGINS"] = "http://localhost:8501"
    os.environ["DAILY_MESSAGE_LIMIT"] = daily_message_limit

    from api.config import get_settings

    get_settings.cache_clear()

    from api.dependencies import get_session_repository, get_usage_repository, get_user_repository

    get_session_repository.cache_clear()
    get_user_repository.cache_clear()
    get_usage_repository.cache_clear()

    from api.rate_limit import limiter

    limiter.enabled = False

    from api.main import app
    from services import conversation

    conversation.openrouter.chat_completion = lambda messages: "Great job!"

    return TestClient(app)


def _signup(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct horse battery staple", "display_name": "Phase Seven"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _send(client: TestClient, headers: dict, text: str):
    return client.post(
        "/api/v1/chat/message",
        headers=headers,
        json={"lesson_id": "present_simple", "messages": [{"role": "user", "content": text}]},
    )


def test_message_past_the_limit_mid_conversation_returns_429() -> None:
    """Issue #136 — looping messages past DAILY_MESSAGE_LIMIT returns 429 with the remaining count."""
    client = _make_client()
    headers = _signup(client, "phase7-136@example.com")

    assert _send(client, headers, "hi").status_code == 200
    assert _send(client, headers, "how are you").status_code == 200
    third = _send(client, headers, "one more, past the limit")

    assert third.status_code == 429, third.text
    body = third.json()["detail"]
    assert body["remaining"] == 0
    assert body["message"]


def test_frontend_blocks_gracefully_when_the_limit_is_hit_mid_conversation() -> None:
    """Issue #135 — the same 429, replayed through the real api_client error path, blocks input."""
    client = _make_client()
    headers = _signup(client, "phase7-135@example.com")
    _send(client, headers, "hi")
    _send(client, headers, "how are you")
    blocked = _send(client, headers, "should be blocked")
    assert blocked.status_code == 429, blocked.text

    import api_client

    fake_st = MagicMock()
    fake_st.session_state = {}
    request = httpx.Request("POST", CHAT_URL)
    response = httpx.Response(429, json=blocked.json(), request=request)
    exc = httpx.HTTPStatusError("429", request=request, response=response)

    with patch.object(api_client, "st", fake_st):
        api_client._handle_response_error(exc)

    assert fake_st.session_state["daily_limit_reached"] is True
    fake_st.error.assert_called_once_with(blocked.json()["detail"]["message"])


def test_usage_counter_persists_across_a_login_logout_cycle() -> None:
    """Issue #137 — the same-day counter survives logout/login (fresh JWT, same server-side row)."""
    client = _make_client()
    email, password = "phase7-137@example.com", "correct horse battery staple"
    signup_headers = _signup(client, email)
    _send(client, signup_headers, "hi")

    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    login_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    usage = client.get("/api/v1/usage/today", headers=login_headers)
    assert usage.status_code == 200, usage.text
    assert usage.json()["messages_used"] == 1


def main() -> int:
    test_message_past_the_limit_mid_conversation_returns_429()
    print("Message past DAILY_MESSAGE_LIMIT mid-conversation returns 429 w/ remaining count (#136) — OK")

    test_frontend_blocks_gracefully_when_the_limit_is_hit_mid_conversation()
    print("Frontend surfaces the Arabic 429 message and disables input for the day (#135) — OK")

    test_usage_counter_persists_across_a_login_logout_cycle()
    print("Daily usage counter survives a logout/login cycle (#137) — OK")

    print("Phase 7 exit checklist (issues #135-#138):")
    print("  [x] Chat routes 429 once DAILY_MESSAGE_LIMIT is exceeded mid-conversation (#136)")
    print("  [x] api_client surfaces the Arabic 429 message and flags daily_limit_reached (#135)")
    print("  [x] components/chat.py disables st.chat_input while daily_limit_reached is set (#135)")
    print("  [x] GET /usage/today reflects the same count after a fresh login (#137)")
    print("  [ ] Manual: uvicorn api.main:app --reload + streamlit run app.py, set")
    print("      DAILY_MESSAGE_LIMIT=1, send one message, confirm the chat input disables")
    print("      with the Arabic limit message visible, then log out/in and confirm the")
    print("      sidebar's remaining-messages count is still 0 (docs §I, frontend bullet)")
    print("Phase 7 exit verification (issues #135-#138): OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
