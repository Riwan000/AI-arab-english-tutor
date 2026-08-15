"""api_client sends mode/difficulty through to the backend (issues #119, #120)."""

from unittest.mock import MagicMock, patch

import api_client


@patch("api_client.httpx.post")
def test_start_chat_includes_difficulty_and_mode_in_payload(mock_post):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"reply": "Hi!", "corrections": []}
    mock_post.return_value = response

    api_client.start_chat(None, difficulty="advanced", mode="free_talk")

    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {"lesson_id": None, "difficulty": "advanced", "mode": "free_talk"}


@patch("api_client.httpx.post")
def test_send_message_includes_difficulty_and_mode_in_payload(mock_post):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"reply": "Hi!", "corrections": []}
    mock_post.return_value = response

    api_client.send_message(None, [], "hello", difficulty="intermediate", mode="free_talk")

    _, kwargs = mock_post.call_args
    payload = kwargs["json"]
    assert payload["lesson_id"] is None
    assert payload["difficulty"] == "intermediate"
    assert payload["mode"] == "free_talk"


@patch("api_client.httpx.post")
def test_save_session_includes_mode_in_payload(mock_post):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"id": 1}
    mock_post.return_value = response

    api_client.save_session(None, [{"role": "user", "content": "hi"}], [], mode="free_talk")

    _, kwargs = mock_post.call_args
    payload = kwargs["json"]
    assert payload["lesson_id"] is None
    assert payload["mode"] == "free_talk"


@patch("api_client.httpx.post")
def test_start_chat_defaults_to_beginner_lesson(mock_post):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"reply": "Hi!", "corrections": []}
    mock_post.return_value = response

    api_client.start_chat("present_simple")

    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {"lesson_id": "present_simple", "difficulty": "beginner", "mode": "lesson"}
