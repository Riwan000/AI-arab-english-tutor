import services.conversation as conversation
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

    def fake_build_messages(lesson, history, start=False, difficulty="beginner", mode="lesson"):
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

    def fake_build_messages(lesson, history, start=False, difficulty="beginner", mode="lesson"):
        captured["lesson_title"] = lesson["title"] if lesson else None
        captured["difficulty"] = difficulty
        captured["mode"] = mode
        return [{"role": "system", "content": "x"}]

    monkeypatch.setattr(conversation, "build_messages", fake_build_messages)
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: "ok")

    conversation.send_message("present_simple", [], "hi")

    assert captured == {"lesson_title": "Present Simple", "difficulty": "beginner", "mode": "lesson"}
