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


def build_messages(
    lesson: dict | None,
    history: list[dict],
    start: bool = False,
    difficulty: str = "beginner",
    mode: str = "lesson",
) -> list[dict]:
    system_content = (
        _build_free_talk_content(difficulty)
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


def _build_free_talk_content(difficulty: str) -> str:
    template = get_free_talk_context_template()

    free_talk_context = template.format(
        student_level="A1–A2 beginner",
        native_language="Arabic",
    )

    difficulty_block = get_difficulty_block(difficulty)

    return f"{get_system_prompt()}\n\n{free_talk_context}\n\n{difficulty_block}"
