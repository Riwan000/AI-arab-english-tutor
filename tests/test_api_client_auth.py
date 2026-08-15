"""An expired or tampered JWT must log the user out cleanly, not strand an error banner (issue #104).

These call the real `api_client._handle_response_error` against a mocked `st`
(same pattern as scripts/verify_phase2_exit.py's test_api_client_journey_mocked),
so the branch under test is production code, not a reimplementation of it.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

import api_client

LOGIN_URL = "http://localhost:8000/api/v1/auth/login"
STALE_TOKEN = "expired-or-tampered-jwt"


def _status_error(status_code: int, detail: str = "Invalid email or password") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", LOGIN_URL)
    response = httpx.Response(status_code, json={"detail": detail}, request=request)
    return httpx.HTTPStatusError(detail, request=request, response=response)


@pytest.fixture
def fake_st():
    """A stand-in for streamlit with a real dict session_state, so writes are assertable."""
    st = MagicMock()
    st.session_state = {}
    with patch.object(api_client, "st", st):
        yield st


def test_401_with_a_live_session_clears_the_token_and_flags_force_logout(fake_st, monkeypatch):
    monkeypatch.setattr(api_client, "_auth_token", STALE_TOKEN)

    api_client._handle_response_error(_status_error(401, "Not authenticated"))

    assert api_client._auth_token is None
    assert fake_st.session_state["force_logout"] is True


def test_401_with_a_live_session_shows_no_error_banner(fake_st, monkeypatch):
    # app.py reacts to force_logout by rerunning into the auth view; an error
    # banner here would be a dead-end message on a screen the user has left.
    monkeypatch.setattr(api_client, "_auth_token", STALE_TOKEN)

    api_client._handle_response_error(_status_error(401, "Not authenticated"))

    fake_st.error.assert_not_called()


def test_401_without_a_token_shows_the_error_and_does_not_force_logout(fake_st, monkeypatch):
    # A 401 with no token set is a plain wrong-password reply from the login
    # form — the user has no session to expire and needs to see why it failed.
    monkeypatch.setattr(api_client, "_auth_token", None)

    api_client._handle_response_error(_status_error(401, "Invalid email or password"))

    assert "force_logout" not in fake_st.session_state
    fake_st.error.assert_called_once_with("Invalid email or password")


def test_non_401_error_with_a_live_session_shows_the_error_and_keeps_the_token(fake_st, monkeypatch):
    monkeypatch.setattr(api_client, "_auth_token", STALE_TOKEN)

    api_client._handle_response_error(_status_error(500, "Server error"))

    assert api_client._auth_token == STALE_TOKEN
    assert "force_logout" not in fake_st.session_state
    fake_st.error.assert_called_once_with("Server error")
