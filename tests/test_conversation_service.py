import json

import pytest

import services.conversation as conversation
from repositories.draft_repo import DraftRepository
from repositories.session_repo import SessionRepository
from services import openrouter


def test_lesson_mode_resolves_lesson_and_calls_llm(monkeypatch):
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: "Hello!")

    response = conversation.start_conversation("present_simple")

    assert response.reply == "Hello!"


def test_free_talk_mode_skips_lesson_lookup(monkeypatch):
    def fail_get_lesson(lesson_id):
        raise AssertionError("lessons.get_lesson should not be called in free_talk mode")

    monkeypatch.setattr(conversation.lessons, "get_lesson", fail_get_lesson)
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: "Hi there!")

    response = conversation.start_conversation(None, mode="free_talk")

    assert response.reply == "Hi there!"


def test_send_message_free_talk_skips_lesson_lookup(monkeypatch):
    def fail_get_lesson(lesson_id):
        raise AssertionError("lessons.get_lesson should not be called in free_talk mode")

    monkeypatch.setattr(conversation.lessons, "get_lesson", fail_get_lesson)
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: "ok")

    response = conversation.send_message(None, [], "hi", mode="free_talk")

    assert response.reply == "ok"


def test_start_conversation_passes_difficulty_and_mode_to_prompt_builder(monkeypatch):
    captured = {}

    def fake_build_messages(lesson, history, start=False, difficulty="beginner", mode="lesson", **kwargs):
        captured["lesson"] = lesson
        captured["difficulty"] = difficulty
        captured["mode"] = mode
        return [{"role": "system", "content": "x"}]

    monkeypatch.setattr(conversation, "build_messages", fake_build_messages)
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: "ok")

    conversation.start_conversation(None, difficulty="advanced", mode="free_talk")

    assert captured == {"lesson": None, "difficulty": "advanced", "mode": "free_talk"}


def test_send_message_defaults_match_previous_lesson_mode_behavior(monkeypatch):
    captured = {}

    def fake_build_messages(lesson, history, start=False, difficulty="beginner", mode="lesson", **kwargs):
        captured["lesson_title"] = lesson["title"] if lesson else None
        captured["difficulty"] = difficulty
        captured["mode"] = mode
        return [{"role": "system", "content": "x"}]


    monkeypatch.setattr(conversation, "build_messages", fake_build_messages)
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: "ok")

    conversation.send_message("present_simple", [], "hi")

    assert captured == {"lesson_title": "Present Simple", "difficulty": "beginner", "mode": "lesson"}


def test_end_session_free_talk_skips_lesson_lookup_and_titles_session(monkeypatch):
    def fail_get_lesson(lesson_id):
        raise AssertionError("lessons.get_lesson should not be called in free_talk mode")

    captured = {}

    def fake_save(self, **kwargs):
        captured.update(kwargs)
        return 1

    monkeypatch.setattr(conversation.lessons, "get_lesson", fail_get_lesson)
    monkeypatch.setattr(SessionRepository, "save", fake_save)

    messages = [{"role": "user", "content": "hi"}]
    result = conversation.end_session(None, messages, [], mode="free_talk")

    assert result is not None
    assert captured["lesson"] == {"id": None, "title": "Free Talk"}


def test_end_session_lesson_mode_resolves_lesson_as_before(monkeypatch):
    captured = {}

    def fake_save(self, **kwargs):
        captured.update(kwargs)
        return 1

    monkeypatch.setattr(SessionRepository, "save", fake_save)

    messages = [{"role": "user", "content": "hi"}]
    result = conversation.end_session("present_simple", messages, [])

    assert result is not None
    assert captured["lesson"]["id"] == "present_simple"
    assert captured["lesson"]["title"] == "Present Simple"


def test_end_session_threads_user_id_to_repository_save(monkeypatch):
    captured = {}

    def fake_save(self, **kwargs):
        captured.update(kwargs)
        return 1

    monkeypatch.setattr(SessionRepository, "save", fake_save)

    messages = [{"role": "user", "content": "hi"}]
    conversation.end_session(None, messages, [], mode="free_talk", user_id=42)

    assert captured["user_id"] == 42


def test_end_session_defaults_user_id_to_none(monkeypatch):
    captured = {}

    def fake_save(self, **kwargs):
        captured.update(kwargs)
        return 1

    monkeypatch.setattr(SessionRepository, "save", fake_save)

    messages = [{"role": "user", "content": "hi"}]
    conversation.end_session("present_simple", messages, [])

    assert captured["user_id"] is None


def test_end_session_threads_mode_to_repository_save(monkeypatch):
    captured = {}

    def fake_save(self, **kwargs):
        captured.update(kwargs)
        return 1

    monkeypatch.setattr(SessionRepository, "save", fake_save)

    messages = [{"role": "user", "content": "hi"}]
    conversation.end_session(None, messages, [], mode="free_talk")

    assert captured["mode"] == "free_talk"


def test_end_session_defaults_mode_to_lesson(monkeypatch):
    captured = {}

    def fake_save(self, **kwargs):
        captured.update(kwargs)
        return 1

    monkeypatch.setattr(SessionRepository, "save", fake_save)

    messages = [{"role": "user", "content": "hi"}]
    conversation.end_session("present_simple", messages, [])

    assert captured["mode"] == "lesson"


# --- session_ending (Feature A) -------------------------------------------------


def test_send_message_threads_session_ending_true_from_llm(monkeypatch):
    raw = json.dumps({"reply": "Bye! See you next time.", "corrections": [], "session_ending": True})
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: raw)

    response = conversation.send_message(None, [], "goodbye", mode="free_talk")

    assert response.session_ending is True


def test_send_message_threads_session_ending_false_from_llm(monkeypatch):
    raw = json.dumps({"reply": "Tell me more!", "corrections": [], "session_ending": False})
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: raw)

    response = conversation.send_message(None, [], "I like pizza", mode="free_talk")

    assert response.session_ending is False


def test_send_message_defaults_session_ending_false_when_response_field_missing(monkeypatch):
    raw = json.dumps({"reply": "Tell me more!", "corrections": []})
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: raw)

    response = conversation.send_message(None, [], "I like pizza", mode="free_talk")

    assert response.session_ending is False


def test_send_message_farewell_keyword_flags_session_ending_even_when_llm_omits_it(monkeypatch):
    """The LLM ignoring the field must not stop an obvious 'bye' from ending the chat."""
    raw = json.dumps({"reply": "Bye!", "corrections": []})
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: raw)

    response = conversation.send_message(None, [], "ok bye", mode="free_talk")

    assert response.session_ending is True


# --- draft persistence (Feature B) ----------------------------------------------


def test_send_message_saves_a_draft_in_free_talk_when_not_ending(monkeypatch):
    raw = json.dumps({"reply": "Nice! Tell me more.", "corrections": [], "session_ending": False})
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: raw)

    captured = {}

    def fake_save(self, user_id, messages, lesson_id=None, mode="free_talk", difficulty=None):
        captured["user_id"] = user_id
        captured["messages"] = messages
        captured["mode"] = mode

    monkeypatch.setattr(DraftRepository, "save", fake_save)
    monkeypatch.setattr(DraftRepository, "delete", lambda self, user_id: pytest.fail("should not delete"))

    conversation.send_message(None, [], "I like pizza", mode="free_talk", user_id=7)

    assert captured["user_id"] == 7
    assert captured["messages"][-1] == {"role": "assistant", "content": "Nice! Tell me more."}
    assert captured["mode"] == "free_talk"


def test_send_message_deletes_draft_when_session_ending(monkeypatch):
    raw = json.dumps({"reply": "Bye!", "corrections": [], "session_ending": True})
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: raw)

    captured = {}
    monkeypatch.setattr(DraftRepository, "delete", lambda self, user_id: captured.setdefault("deleted_for", user_id))
    monkeypatch.setattr(DraftRepository, "save", lambda self, *a, **k: pytest.fail("should not save"))

    conversation.send_message(None, [], "bye", mode="free_talk", user_id=7)

    assert captured["deleted_for"] == 7


def test_send_message_skips_draft_persistence_without_user_id(monkeypatch):
    raw = json.dumps({"reply": "ok", "corrections": [], "session_ending": False})
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: raw)
    monkeypatch.setattr(DraftRepository, "save", lambda self, *a, **k: pytest.fail("should not save"))
    monkeypatch.setattr(DraftRepository, "delete", lambda self, *a, **k: pytest.fail("should not delete"))

    conversation.send_message(None, [], "hi", mode="free_talk", user_id=None)


def test_send_message_skips_draft_persistence_in_lesson_mode(monkeypatch):
    raw = json.dumps({"reply": "ok", "corrections": [], "session_ending": False})
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: raw)
    monkeypatch.setattr(DraftRepository, "save", lambda self, *a, **k: pytest.fail("should not save"))
    monkeypatch.setattr(DraftRepository, "delete", lambda self, *a, **k: pytest.fail("should not delete"))

    conversation.send_message("present_simple", [], "hi", mode="lesson", user_id=7)


def test_end_session_deletes_draft_after_successful_save(monkeypatch):
    monkeypatch.setattr(SessionRepository, "save", lambda self, **kwargs: 1)

    captured = {}
    monkeypatch.setattr(DraftRepository, "delete", lambda self, user_id: captured.setdefault("deleted_for", user_id))

    messages = [{"role": "user", "content": "hi"}]
    conversation.end_session(None, messages, [], mode="free_talk", user_id=9)

    assert captured["deleted_for"] == 9


def test_end_session_skips_draft_delete_without_user_id(monkeypatch):
    monkeypatch.setattr(SessionRepository, "save", lambda self, **kwargs: 1)
    monkeypatch.setattr(DraftRepository, "delete", lambda self, *a, **k: pytest.fail("should not delete"))

    messages = [{"role": "user", "content": "hi"}]
    conversation.end_session(None, messages, [], mode="free_talk")
