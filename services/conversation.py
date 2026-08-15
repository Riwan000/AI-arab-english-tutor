"""Chat orchestration — no HTTP, no UI, no direct DB access from routes."""

import os

from models.conversation import ChatResponse, SessionSummary
from models.feedback import GrammarFeedback
from prompts.prompt_builder import build_messages
from repositories.session_repo import SessionRepository
from services import grammar, lessons, openrouter, scoring


def start_conversation(
    lesson_id: str | None,
    difficulty: str = "beginner",
    mode: str = "lesson",
) -> ChatResponse:
    """Build start prompt, call LLM, return clean reply. Loads a lesson only in lesson mode."""
    lesson_dict = _resolve_lesson(lesson_id, mode)

    messages = build_messages(lesson_dict, [], start=True, difficulty=difficulty, mode=mode)
    raw = openrouter.chat_completion(messages)
    corrections = grammar.extract_feedback(raw)
    reply = grammar.strip_json_from_response(raw)

    return ChatResponse(reply=reply, corrections=corrections)


def send_message(
    lesson_id: str | None,
    messages: list[dict],
    user_text: str,
    difficulty: str = "beginner",
    mode: str = "lesson",
) -> ChatResponse:
    """Append user message, call LLM, parse corrections, return clean reply."""
    lesson_dict = _resolve_lesson(lesson_id, mode)

    history = [*messages, {"role": "user", "content": user_text}]
    prompt_messages = build_messages(lesson_dict, history, difficulty=difficulty, mode=mode)
    raw = openrouter.chat_completion(prompt_messages)
    corrections = grammar.extract_feedback(raw)
    reply = grammar.strip_json_from_response(raw)

    return ChatResponse(reply=reply, corrections=corrections)


def _resolve_lesson(lesson_id: str | None, mode: str) -> dict | None:
    """Look up the lesson in lesson mode only — Free Talk has no lesson to resolve."""
    if mode != "lesson":
        return None
    lesson = lessons.get_lesson(lesson_id)
    return lesson.model_dump()


def end_session(
    lesson_id: str,
    messages: list[dict],
    mistakes: list,
) -> SessionSummary | None:
    """Score session, persist via repository, return summary."""
    if not messages:
        return None

    lesson = lessons.get_lesson(lesson_id)
    lesson_dict = lesson.model_dump()

    summary = scoring.calculate_session_summary(
        messages=messages,
        mistakes=mistakes,
        lesson_title=lesson.title,
    )

    conversation_id = SessionRepository().save(
        lesson=lesson_dict,
        messages=messages,
        mistakes=mistakes,
        summary=summary,
        model_used=os.getenv("DEFAULT_MODEL", openrouter.DEFAULT_MODEL),
    )

    if conversation_id is None:
        return None

    return SessionSummary(
        id=conversation_id,
        grammar_score=summary["grammar"],
        exchange_count=summary["exchanges"],
        mistake_count=summary["mistake_count"],
        vocabulary=summary.get("vocabulary", []),
        recommendation=summary.get("recommendation"),
        mistake_types=summary.get("mistake_types", []),
    )
