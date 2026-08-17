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

    return _parse_corrections(data.get("corrections", []))


def _parse_corrections(raw_corrections: list) -> list[GrammarFeedback]:
    if not isinstance(raw_corrections, list):
        return []

    feedback: list[GrammarFeedback] = []
    for item in raw_corrections:
        try:
            feedback.append(GrammarFeedback(**item))
        except (TypeError, ValueError):
            continue
    return feedback


_REPLY_KEY_FALLBACKS = ("reply", "message", "text", "response")
_GENERIC_FALLBACK_REPLY = "Sorry, I had trouble with that — could you try again?"


def parse_response(response: str) -> tuple[str, list[GrammarFeedback]]:
    """Split an LLM turn into visible reply text and structured corrections.

    The model is asked (via response_format=json_object) to return the whole
    turn as one {"reply": ..., "corrections": [...]} object, so a syntactically
    valid JSON object is the expected shape. If it's not JSON at all, that
    means the model ignored the instruction and fell back to the older
    convention of prose with a trailing ```json fenced block, so that raw text
    is parsed with the legacy regex path instead.

    A JSON object that IS valid but doesn't carry a "reply" string (wrong key
    name, or the model just got the shape wrong) is deliberately NOT treated
    as legacy prose — running the legacy regex over it would be a no-op (no
    ```json fence to strip) and dump the raw JSON straight into the visible
    reply, reproducing the exact leak this function exists to prevent. A
    handful of plausible alternate keys are tried first; failing those, a
    generic apology is shown rather than ever surfacing raw JSON.
    """
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        return strip_json_from_response(response), extract_feedback(response)

    if not isinstance(data, dict):
        return strip_json_from_response(response), extract_feedback(response)

    reply = next(
        (data[key] for key in _REPLY_KEY_FALLBACKS if isinstance(data.get(key), str)),
        _GENERIC_FALLBACK_REPLY,
    )
    return reply, _parse_corrections(data.get("corrections", []))
