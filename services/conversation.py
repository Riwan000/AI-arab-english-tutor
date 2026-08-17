"""Chat orchestration — no HTTP, no UI, no direct DB access from routes."""

import os

from models.conversation import ChatResponse, SessionSummary
from models.feedback import GrammarFeedback
from prompts.prompt_builder import build_messages, format_past_context
from repositories.session_repo import SessionRepository
from services import grammar, lessons, openrouter, scoring


def start_conversation(
    lesson_id: str | None,
    difficulty: str = "beginner",
    mode: str = "lesson",
    user_id: int | None = None,
) -> ChatResponse:
    """Build start prompt, call LLM, return clean reply. Loads a lesson only in lesson mode."""
    lesson_dict = _resolve_lesson(lesson_id, mode)

    past_context = None
    if mode == "free_talk" and user_id is not None:
        past_profile = SessionRepository().get_user_learning_profile(user_id)
        past_context = format_past_context(past_profile)

    messages = build_messages(
        lesson_dict,
        [],
        start=True,
        difficulty=difficulty,
        mode=mode,
        past_context=past_context,
    )
    raw = openrouter.chat_completion(messages)
    reply, corrections = grammar.parse_response(raw)

    return ChatResponse(reply=reply, corrections=corrections)


def send_message(
    lesson_id: str | None,
    messages: list[dict],
    user_text: str,
    difficulty: str = "beginner",
    mode: str = "lesson",
    user_id: int | None = None,
) -> ChatResponse:
    """Append user message, call LLM, parse corrections, return clean reply."""
    lesson_dict = _resolve_lesson(lesson_id, mode)

    past_context = None
    if mode == "free_talk" and user_id is not None:
        past_profile = SessionRepository().get_user_learning_profile(user_id)
        past_context = format_past_context(past_profile)

    history = [*messages, {"role": "user", "content": user_text}]
    prompt_messages = build_messages(
        lesson_dict,
        history,
        difficulty=difficulty,
        mode=mode,
        past_context=past_context,
    )
    raw = openrouter.chat_completion(prompt_messages)
    reply, corrections = grammar.parse_response(raw)

    return ChatResponse(reply=reply, corrections=corrections)



def _resolve_lesson(lesson_id: str | None, mode: str) -> dict | None:
    """Look up the lesson in lesson mode only — Free Talk has no lesson to resolve."""
    if mode != "lesson":
        return None
    lesson = lessons.get_lesson(lesson_id)
    return lesson.model_dump()


def end_session(
    lesson_id: str | None,
    messages: list[dict],
    mistakes: list,
    mode: str = "lesson",
    user_id: int | None = None,
) -> SessionSummary | None:
    """Score session, persist via repository, return summary. Free Talk has no lesson to look up."""
    if not messages:
        return None

    if mode == "free_talk":
        lesson_dict, lesson_title = None, "Free Talk"
    else:
        lesson = lessons.get_lesson(lesson_id)
        lesson_dict, lesson_title = lesson.model_dump(), lesson.title

    summary = scoring.calculate_session_summary(
        messages=messages,
        mistakes=mistakes,
        lesson_title=lesson_title,
    )

    conversation_id = SessionRepository().save(
        lesson=lesson_dict or {"id": None, "title": "Free Talk"},
        messages=messages,
        mistakes=mistakes,
        summary=summary,
        model_used=os.getenv("DEFAULT_MODEL", openrouter.DEFAULT_MODEL),
        user_id=user_id,
        mode=mode,
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
