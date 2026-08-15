"""Mode/difficulty threading through the chat and session request schemas (issues #119, #120)."""

import pytest
from pydantic import ValidationError

from api.schemas.chat import ChatMessageRequest, ChatStartRequest
from api.schemas.session import SessionCreateRequest


def test_chat_start_request_defaults_to_beginner_lesson():
    request = ChatStartRequest(lesson_id="present_simple")
    assert request.difficulty == "beginner"
    assert request.mode == "lesson"


def test_chat_start_request_accepts_free_talk_with_no_lesson_id():
    request = ChatStartRequest(mode="free_talk", difficulty="advanced")
    assert request.lesson_id is None
    assert request.mode == "free_talk"
    assert request.difficulty == "advanced"


def test_chat_start_request_rejects_invalid_difficulty():
    with pytest.raises(ValidationError):
        ChatStartRequest(lesson_id="present_simple", difficulty="expert")


def test_chat_start_request_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        ChatStartRequest(lesson_id="present_simple", mode="quiz")


def test_chat_message_request_defaults_to_beginner_lesson():
    request = ChatMessageRequest(
        lesson_id="present_simple",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert request.difficulty == "beginner"
    assert request.mode == "lesson"


def test_chat_message_request_accepts_free_talk_with_no_lesson_id():
    request = ChatMessageRequest(
        mode="free_talk",
        difficulty="intermediate",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert request.lesson_id is None
    assert request.mode == "free_talk"
    assert request.difficulty == "intermediate"


def test_chat_message_request_rejects_invalid_difficulty():
    with pytest.raises(ValidationError):
        ChatMessageRequest(
            lesson_id="present_simple",
            difficulty="master",
            messages=[{"role": "user", "content": "hi"}],
        )


def test_chat_message_request_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        ChatMessageRequest(
            lesson_id="present_simple",
            mode="quiz",
            messages=[{"role": "user", "content": "hi"}],
        )


def test_session_create_request_defaults_mode_to_lesson():
    request = SessionCreateRequest(messages=[{"role": "user", "content": "hi"}])
    assert request.mode == "lesson"


def test_session_create_request_accepts_free_talk_mode():
    request = SessionCreateRequest(
        mode="free_talk",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert request.mode == "free_talk"
    assert request.lesson_id is None


def test_session_create_request_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        SessionCreateRequest(mode="quiz", messages=[{"role": "user", "content": "hi"}])
