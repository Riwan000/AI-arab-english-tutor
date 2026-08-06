"""Builds lesson-aware prompts for the OpenRouter API."""

from prompts.system_prompt import SYSTEM_PROMPT


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
        messages.append({
            "role": "user",
            "content": (
                f"Start a guided conversation to practice {lesson['title']}. "
                "Greet the student and ask your first simple question."
            ),
        })

    return messages


def _build_system_content(lesson: dict) -> str:
    rules = "\n".join(f"- {rule}" for rule in lesson.get("grammar_rules", []))
    vocabulary = ", ".join(lesson.get("allowed_vocabulary", []))

    return f"""{SYSTEM_PROMPT}

## Current Lesson
Title: {lesson['title']}
Description: {lesson['description']}

## Grammar Rules
{rules}

## Allowed Vocabulary
{vocabulary}

## Student Level
A1–A2 beginner

## Native Language
Arabic
"""
