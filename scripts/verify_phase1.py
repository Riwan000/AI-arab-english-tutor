"""Quick verification for Phase 1 service refactor."""

from pathlib import Path
from unittest.mock import patch

from services.conversation import end_session, send_message, start_conversation
from services.errors import LessonNotFoundError
from services.grammar import extract_feedback, strip_json_from_response
from services.lessons import get_lesson, list_lessons


def test_grammar_strip_and_extract() -> None:
    raw = (
        "Great try! Keep going.\n"
        '```json\n{"corrections": [{"mistake_type": "Verb Form", '
        '"wrong_text": "I eating", "correct_text": "I eat", '
        '"english_explanation": "e", "arabic_explanation": "a"}]}\n```'
    )
    clean = strip_json_from_response(raw)
    assert "```json" not in clean
    assert "Great try!" in clean
    feedback = extract_feedback(raw)
    assert len(feedback) == 1
    assert feedback[0].correct_text == "I eat"


def test_lessons() -> None:
    assert len(list_lessons()) == 5
    assert get_lesson("present_simple").title == "Present Simple"
    try:
        get_lesson("missing")
        raise AssertionError("expected LessonNotFoundError")
    except LessonNotFoundError:
        pass


def test_conversation_mocked() -> None:
    with patch("services.openrouter.chat_completion") as mock_llm:
        mock_llm.return_value = "Hello! Tell me about your routine."
        start = start_conversation("present_simple")
        assert start.reply == "Hello! Tell me about your routine."
        assert start.corrections == []

        mock_llm.return_value = (
            "Almost!\n"
            '```json\n{"corrections": [{"mistake_type": "Verb Form", '
            '"wrong_text": "I eating", "correct_text": "I eat", '
            '"english_explanation": "e", "arabic_explanation": "a"}]}\n```'
        )
        reply = send_message(
            "present_simple",
            [{"role": "assistant", "content": "Hi"}],
            "I eating",
        )
        assert "```json" not in reply.reply
        assert len(reply.corrections) == 1


def test_end_session() -> None:
    import os
    import tempfile

    import services.database as dbmod

    tmpdir = tempfile.mkdtemp()
    os.environ["DATABASE_PATH"] = str(Path(tmpdir) / "test.db")
    dbmod.DB_PATH = Path(os.environ["DATABASE_PATH"])

    messages = [
        {
            "role": "assistant",
            "content": "Hi",
            "timestamp": "2026-08-07T01:00:00+00:00",
            "lesson_id": "present_simple",
        },
        {
            "role": "user",
            "content": "I eat",
            "timestamp": "2026-08-07T01:01:00+00:00",
            "lesson_id": "present_simple",
        },
    ]
    result = end_session("present_simple", messages, [])
    assert result is not None
    assert result.id > 0


if __name__ == "__main__":
    test_grammar_strip_and_extract()
    test_lessons()
    test_conversation_mocked()
    test_end_session()
    print("Phase 1 verification: OK")
