"""A 429 daily-limit response must surface the Arabic message and flag the
session so components/chat.py can disable further input for the day (issue #135).

Same pattern as test_api_client_auth.py: call the real
`api_client._handle_response_error` against a mocked `st`, so the branch under
test is production code, not a reimplementation of it.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

import api_client

CHAT_URL = "http://localhost:8000/api/v1/chat/message"
ARABIC_LIMIT_MESSAGE = "لقد وصلت إلى الحد اليومي لعدد الرسائل. حاول مرة أخرى غدًا."


def _status_error(status_code: int, detail) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", CHAT_URL)
    response = httpx.Response(status_code, json={"detail": detail}, request=request)
    return httpx.HTTPStatusError(str(detail), request=request, response=response)


@pytest.fixture
def fake_st():
    """A stand-in for streamlit with a real dict session_state, so writes are assertable."""
    st = MagicMock()
    st.session_state = {}
    with patch.object(api_client, "st", st):
        yield st


def test_daily_limit_429_shows_the_arabic_message(fake_st):
    detail = {"message": ARABIC_LIMIT_MESSAGE, "remaining": 0}

    api_client._handle_response_error(_status_error(429, detail))

    fake_st.error.assert_called_once_with(ARABIC_LIMIT_MESSAGE)


def test_daily_limit_429_flags_the_session_state(fake_st):
    detail = {"message": ARABIC_LIMIT_MESSAGE, "remaining": 0}

    api_client._handle_response_error(_status_error(429, detail))

    assert fake_st.session_state["daily_limit_reached"] is True


def test_rate_limiter_429_does_not_flag_daily_limit(fake_st):
    # slowapi's 429 body is a plain string, not the {"message", "remaining"}
    # shape DailyLimitExceededError produces — must not be misread as the
    # daily-usage limit.
    api_client._handle_response_error(
        _status_error(429, "Too many requests. Please wait a moment and try again.")
    )

    assert "daily_limit_reached" not in fake_st.session_state
    fake_st.error.assert_called_once_with("Too many requests. Please wait a moment and try again.")


def test_non_429_dict_detail_is_not_treated_as_daily_limit(fake_st):
    api_client._handle_response_error(_status_error(500, {"message": "boom", "remaining": 3}))

    assert "daily_limit_reached" not in fake_st.session_state
    fake_st.error.assert_called_once_with("boom")
