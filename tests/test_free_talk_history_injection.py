from prompts.prompt_builder import build_messages, format_past_context
from repositories.session_repo import SessionRepository
from services import conversation


def test_format_past_context_with_empty_profile():
    assert format_past_context(None) == "No prior session history recorded."
    assert format_past_context({}) == "No prior session history recorded."
    assert format_past_context({"recent_sessions": [], "top_mistakes": []}) == "No prior session history recorded."


def test_format_past_context_with_sessions_and_mistakes():
    profile = {
        "recent_sessions": [
            {
                "lesson_title": "Present Simple",
                "grammar_score": 85,
                "recommendation": "Practice subject-verb agreement.",
            }
        ],
        "top_mistakes": ["verb_tense", "preposition_use"],
    }
    result = format_past_context(profile)
    assert "Present Simple" in result
    assert "85%" in result
    assert "Practice subject-verb agreement." in result
    assert "verb_tense" in result
    assert "preposition_use" in result


def test_build_messages_free_talk_injects_past_context():
    past_text = "Recent Sessions Completed:\n- Past Continuous (Grammar Score: 90%)"
    messages = build_messages(None, [], mode="free_talk", past_context=past_text)

    assert messages[0]["role"] == "system"
    assert past_text in messages[0]["content"]


def test_start_conversation_free_talk_threads_user_id(monkeypatch):
    called = {}

    def fake_profile(self, user_id):
        called["user_id"] = user_id
        return {
            "recent_sessions": [
                {"lesson_title": "Free Talk", "grammar_score": 75, "recommendation": "Keep going."}
            ],
            "top_mistakes": ["articles"],
        }

    monkeypatch.setattr(SessionRepository, "get_user_learning_profile", fake_profile)
    monkeypatch.setattr("services.openrouter.chat_completion_stream", lambda msgs: iter(["Hello there!"]))

    res = conversation.start_conversation(None, mode="free_talk", user_id=42)

    assert called.get("user_id") == 42
    assert res.reply == "Hello there!"


def test_database_get_user_learning_profile():
    user_id = 999
    profile = SessionRepository().get_user_learning_profile(user_id)
    assert "recent_sessions" in profile
    assert "top_mistakes" in profile
    assert profile["recent_sessions"] == []
    assert profile["top_mistakes"] == []
