from prompts.prompt_builder import MAX_HISTORY_MESSAGES, build_messages


LESSON = {
    "id": "present-simple",
    "title": "Present Simple",
    "description": "Talking about habits and routines.",
    "grammar_rules": ["Use base verb for I/you/we/they."],
    "allowed_vocabulary": ["eat", "go", "work"],
}


def test_lesson_mode_default_matches_previous_behavior():
    messages = build_messages(LESSON, [])

    assert messages[0]["role"] == "system"
    assert "Present Simple" in messages[0]["content"]


def test_lesson_mode_appends_difficulty_block():
    messages = build_messages(LESSON, [], difficulty="advanced")

    assert "Advanced" in messages[0]["content"]
    assert "Present Simple" in messages[0]["content"]


def test_lesson_mode_start_uses_lesson_title():
    messages = build_messages(LESSON, [], start=True)

    assert messages[-1]["role"] == "user"
    assert "Present Simple" in messages[-1]["content"]


def test_free_talk_mode_uses_free_talk_context_not_lesson():
    messages = build_messages(None, [], mode="free_talk")

    assert "Free Talk" in messages[0]["content"]
    assert "## Current Lesson" not in messages[0]["content"]


def test_free_talk_mode_still_appends_difficulty_block():
    messages = build_messages(None, [], difficulty="intermediate", mode="free_talk")

    assert "Intermediate" in messages[0]["content"]


def test_free_talk_mode_start_does_not_require_lesson_title():
    messages = build_messages(None, [], start=True, mode="free_talk")

    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"]


def test_history_is_preserved_between_system_and_start_message():
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]

    messages = build_messages(LESSON, history)

    assert messages[1:] == history


def test_history_beyond_trailing_window_is_truncated():
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
        for i in range(MAX_HISTORY_MESSAGES + 5)
    ]

    messages = build_messages(LESSON, history)

    assert messages[1:] == history[-MAX_HISTORY_MESSAGES:]
    assert len(messages) - 1 == MAX_HISTORY_MESSAGES
