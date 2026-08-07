"""Parses grammar feedback from LLM responses."""

import json
import re

from models.feedback import GrammarFeedback

JSON_BLOCK_PATTERN = re.compile(r"```json\s*\{.*?\}\s*```", re.DOTALL)


def strip_json_from_response(response: str) -> str:
    """Remove JSON correction block from visible reply text."""
    return JSON_BLOCK_PATTERN.sub("", response).strip()


def extract_feedback(response: str) -> list[GrammarFeedback]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    corrections = data.get("corrections", [])
    feedback: list[GrammarFeedback] = []
    for item in corrections:
        try:
            feedback.append(GrammarFeedback(**item))
        except (TypeError, ValueError):
            continue
    return feedback
