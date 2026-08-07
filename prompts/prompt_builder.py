"""Builds lesson-aware prompts for the OpenRouter API."""

from prompts.prompt_loader import (
    get_lesson_context_template,
    get_start_message_template,
    get_system_prompt,
)


def build_messages(
    lesson: dict,
    history: list[dict],
    start: bool = False,
) -> list[dict]:
    system_content = _build_system_content(lesson)
    messages: list[dict] = [{"role": "system", "content": system_content}]

    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    if start:
        template = get_start_message_template()
        messages.append({
            "role": "user",
            "content": template.format(title=lesson["title"]),
        })

    return messages


def _build_system_content(lesson: dict) -> str:
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

    return f"{get_system_prompt()}\n\n{lesson_context}"
