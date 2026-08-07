"""Verification for api_client HTTP methods (issue #47)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import api_client


def _mock_st(base: str = "http://test-backend:9000") -> MagicMock:
    fake_st = MagicMock()
    fake_st.secrets.get.return_value = base
    return fake_st


def _response(status: int, json_data: dict) -> httpx.Response:
    return httpx.Response(
        status,
        json=json_data,
        request=httpx.Request("GET", "http://test-backend:9000"),
    )


def test_health_check() -> None:
    fake_st = _mock_st()
    response = _response(200, {"status": "ok", "version": "1.0.0", "model": "test"})
    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.get", return_value=response) as mock_get:
            assert api_client.health_check() is True
            mock_get.assert_called_once_with(
                "http://test-backend:9000/api/v1/health",
                timeout=api_client.DEFAULT_TIMEOUT,
            )


def test_list_lessons() -> None:
    fake_st = _mock_st()
    lessons = [{"id": "present_simple", "title": "Present Simple", "description": "..."}]
    response = _response(200, {"lessons": lessons})
    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.get", return_value=response) as mock_get:
            result = api_client.list_lessons()
            assert result == lessons
            mock_get.assert_called_once_with(
                "http://test-backend:9000/api/v1/lessons",
                params=None,
                timeout=api_client.DEFAULT_TIMEOUT,
            )


def test_get_lesson() -> None:
    fake_st = _mock_st()
    lesson = {"id": "present_simple", "title": "Present Simple", "description": "..."}
    response = _response(200, lesson)
    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.get", return_value=response) as mock_get:
            result = api_client.get_lesson("present_simple")
            assert result == lesson
            mock_get.assert_called_once_with(
                "http://test-backend:9000/api/v1/lessons/present_simple",
                params=None,
                timeout=api_client.DEFAULT_TIMEOUT,
            )


def test_start_chat() -> None:
    fake_st = _mock_st()
    body = {"reply": "Hello!", "corrections": []}
    response = _response(200, body)
    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.post", return_value=response) as mock_post:
            result = api_client.start_chat("present_simple")
            assert result == body
            mock_post.assert_called_once_with(
                "http://test-backend:9000/api/v1/chat/start",
                json={"lesson_id": "present_simple"},
                timeout=api_client.CHAT_TIMEOUT,
            )


def test_send_message() -> None:
    fake_st = _mock_st()
    body = {"reply": "Almost!", "corrections": [{"mistake_type": "Verb Form"}]}
    response = _response(200, body)
    history = [
        {"role": "assistant", "content": "Hi", "feedback": []},
        {"role": "user", "content": "old", "timestamp": "2026-08-07T01:00:00+00:00"},
    ]
    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.post", return_value=response) as mock_post:
            result = api_client.send_message("present_simple", history, "I eating")
            assert result == body
            mock_post.assert_called_once_with(
                "http://test-backend:9000/api/v1/chat/message",
                json={
                    "lesson_id": "present_simple",
                    "messages": [
                        {"role": "assistant", "content": "Hi"},
                        {
                            "role": "user",
                            "content": "old",
                            "timestamp": "2026-08-07T01:00:00+00:00",
                        },
                        {"role": "user", "content": "I eating"},
                    ],
                },
                timeout=api_client.CHAT_TIMEOUT,
            )


def test_save_session() -> None:
    fake_st = _mock_st()
    body = {"id": 1, "grammar_score": 90, "exchange_count": 2, "mistake_count": 0}
    response = _response(201, body)
    messages = [
        {
            "role": "assistant",
            "content": "Hi",
            "timestamp": "2026-08-07T01:00:00+00:00",
            "feedback": [],
        },
        {"role": "user", "content": "I eat", "timestamp": "2026-08-07T01:01:00+00:00"},
    ]
    mistakes = [
        {
            "mistake_type": "Verb Form",
            "wrong_text": "I eating",
            "correct_text": "I eat",
            "english_explanation": "e",
            "arabic_explanation": "a",
            "tip": "",
            "message_index": 1,
        }
    ]
    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.post", return_value=response) as mock_post:
            result = api_client.save_session("present_simple", messages, mistakes)
            assert result == body
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["lesson_id"] == "present_simple"
            assert len(call_kwargs["json"]["messages"]) == 2
            assert call_kwargs["json"]["mistakes"][0]["correct_text"] == "I eat"


def test_list_sessions() -> None:
    fake_st = _mock_st()
    sessions = [{"id": 1, "lesson_id": "present_simple", "lesson_title": "Present Simple"}]
    response = _response(200, {"sessions": sessions})
    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.get", return_value=response) as mock_get:
            result = api_client.list_sessions(limit=5)
            assert result == sessions
            mock_get.assert_called_once_with(
                "http://test-backend:9000/api/v1/sessions",
                params={"limit": 5},
                timeout=api_client.DEFAULT_TIMEOUT,
            )


def test_get_session() -> None:
    fake_st = _mock_st()
    session = {"id": 1, "lesson_id": "present_simple", "grammar_score": 90}
    response = _response(200, session)
    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.get", return_value=response) as mock_get:
            result = api_client.get_session(1)
            assert result == session
            mock_get.assert_called_once_with(
                "http://test-backend:9000/api/v1/sessions/1",
                params=None,
                timeout=api_client.DEFAULT_TIMEOUT,
            )


def test_base_url_strips_slash() -> None:
    fake_st = _mock_st("http://localhost:8000/")
    with patch.object(api_client, "st", fake_st):
        assert api_client.base_url() == "http://localhost:8000"


def test_health_check_returns_false_on_error() -> None:
    fake_st = _mock_st()
    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.get", side_effect=httpx.RequestError("down")):
            assert api_client.health_check() is False


def test_send_message_timeout_returns_fallback() -> None:
    fake_st = _mock_st()
    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.post", side_effect=httpx.TimeoutException("slow")):
            result = api_client.send_message("present_simple", [], "hi")
            assert result == {"reply": "", "corrections": []}
            fake_st.error.assert_called_once()


def test_list_lessons_http_error_returns_empty() -> None:
    fake_st = _mock_st()
    request = httpx.Request("GET", "http://test-backend:9000/api/v1/lessons")
    response = httpx.Response(502, json={"detail": "Server error"}, request=request)
    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.get", return_value=response):
            result = api_client.list_lessons()
            assert result == []
            fake_st.error.assert_called_once_with("Server error")


if __name__ == "__main__":
    test_health_check()
    test_list_lessons()
    test_get_lesson()
    test_start_chat()
    test_send_message()
    test_save_session()
    test_list_sessions()
    test_get_session()
    test_base_url_strips_slash()
    test_health_check_returns_false_on_error()
    test_send_message_timeout_returns_fallback()
    test_list_lessons_http_error_returns_empty()
    print("api_client verification (issues #47–#48): OK")
