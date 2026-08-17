"""Builds lesson-aware prompts for the OpenRouter API."""

from prompts.prompt_loader import (
    get_difficulty_block,
    get_free_talk_context_template,
    get_lesson_context_template,
    get_start_message_template,
    get_system_prompt,
)

FREE_TALK_START_MESSAGE = (
    "Start the conversation. Greet the student and open with a real-world topic."
)

# Trailing-window cap on how much history actually reaches the LLM prompt, independent
# of (and much tighter than) the schema's max message-list length — bounds per-turn
# prompt cost even when a session sends the schema's full history every turn.
MAX_HISTORY_MESSAGES = 20


def format_past_context(past_profile: dict | None) -> str:
    """Format past session history and top mistake patterns into prompt text."""
    if not past_profile:
        return "No prior session history recorded."

    sessions = past_profile.get("recent_sessions", [])
    top_mistakes = past_profile.get("top_mistakes", [])

    if not sessions and not top_mistakes:
        return "No prior session history recorded."

    parts = []

    if sessions:
        parts.append("Recent Sessions Completed:")
        for s in sessions:
            title = s.get("lesson_title", "Session")
            score = f"{s['grammar_score']}%" if s.get("grammar_score") is not None else "N/A"
            rec = f" — Recommendation: {s['recommendation']}" if s.get("recommendation") else ""
            parts.append(f"- {title} (Grammar Score: {score}){rec}")

        # Last couple of sessions' vocabulary stands in for "topics discussed"
        # (no separate topic field is stored), so free-talk still feels
        # continuous even in a brand-new, non-resumed session.
        recent_topics = [
            f"{s.get('lesson_title', 'Session')}: {', '.join(s['vocabulary'][:5])}"
            for s in sessions[:2]
            if s.get("vocabulary")
        ]
        if recent_topics:
            parts.append("Recently Discussed Topics/Vocabulary:")
            for topic in recent_topics:
                parts.append(f"- {topic}")

    if top_mistakes:
        parts.append("Frequent Weak Spots & Mistake Patterns to Reinforce:")
        for m in top_mistakes:
            parts.append(f"- {m}")

    return "\n".join(parts)


def build_messages(
    lesson: dict | None,
    history: list[dict],
    start: bool = False,
    difficulty: str = "beginner",
    mode: str = "lesson",
    past_context: str | None = None,
) -> list[dict]:
    system_content = (
        _build_free_talk_content(difficulty, past_context=past_context)
        if mode == "free_talk"
        else _build_system_content(lesson, difficulty)
    )
    messages: list[dict] = [{"role": "system", "content": system_content}]

    for msg in history[-MAX_HISTORY_MESSAGES:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    if start:
        if mode == "free_talk":
            content = FREE_TALK_START_MESSAGE
        else:
            template = get_start_message_template()
            content = template.format(title=lesson["title"])
        messages.append({"role": "user", "content": content})

    return messages


def _build_system_content(lesson: dict, difficulty: str) -> str:
    rules = "\n".join(f"- {rule}" for rule in lesson.get("grammar_rules", []))
    vocabulary = ", ".join(lesson.get("allowed_vocabulary", []))
    template = get_lesson_context_template()

    lesson_context = template.format(
        title=lesson["title"],
        description=lesson["description"],
        grammar_rules=rules,
        vocabulary=vocabulary,
        student_level="A1–A2 beginner",
        native_language="Arabic",
    )

    difficulty_block = get_difficulty_block(difficulty)

    return f"{get_system_prompt()}\n\n{lesson_context}\n\n{difficulty_block}"


def _build_free_talk_content(difficulty: str, past_context: str | None = None) -> str:
    template = get_free_talk_context_template()

    ctx = past_context if past_context else "No prior session history recorded."

    free_talk_context = template.format(
        student_level="A1–A2 beginner",
        native_language="Arabic",
        past_context=ctx,
    )

    difficulty_block = get_difficulty_block(difficulty)

    # Appended explicitly rather than relying solely on a {past_context}
    # placeholder inside the template — the free-talk template's own
    # placeholders can change independently of this, and str.format()
    # silently drops unused kwargs instead of erroring, so a missing
    # placeholder there would otherwise fail silently.
    return (
        f"{get_system_prompt()}\n\n{free_talk_context}\n\n"
        f"## Student History\n{ctx}\n\n{difficulty_block}"
    )

