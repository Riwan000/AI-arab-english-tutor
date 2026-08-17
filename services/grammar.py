"""Parses grammar feedback from LLM responses."""

import json
import re

from models.feedback import GrammarFeedback

JSON_BLOCK_PATTERN = re.compile(r"```json\s*\{.*?\}\s*```", re.DOTALL)


def strip_json_from_response(response: str) -> str:
    """Remove JSON correction block from visible reply text."""
    return JSON_BLOCK_PATTERN.sub("", response).strip()


def _extract_fenced_json_block(response: str) -> dict | None:
    """Parse the trailing ```json fenced block legacy-shaped replies use.

    Shared by extract_feedback and extract_session_ending's fallback path so
    there's exactly one regex for "find the fenced JSON block" instead of two
    that could quietly drift apart. Returns None for anything that isn't a
    JSON object — no fence, malformed JSON, or a fenced value that isn't a
    dict (e.g. a bare list) — never raises.
    """
    match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    return data if isinstance(data, dict) else None


def extract_feedback(response: str) -> list[GrammarFeedback]:
    data = _extract_fenced_json_block(response)
    if data is None:
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


FAREWELL_KEYWORDS = (
    "bye",
    "goodbye",
    "good bye",
    "see you",
    "that's all for today",
    "thats all for today",
    "that is all for today",
    "i'm done",
    "im done",
    "i am done",
    "gotta go",
    "have to go",
    "talk to you later",
    "مع السلامة",
    "باي",
    "خلصت",
    "إلى اللقاء",
    "الى اللقاء",
)


def contains_farewell_keyword(text: str) -> bool:
    """Cheap substring check for an obvious English/Arabic farewell.

    Fallback for services.conversation.send_message: OR'd with the LLM's
    session_ending flag so a conversation can still end on an obvious "bye"
    even if the model forgets to set the field. Deliberately small and
    literal — no NLP, just a substring match against FAREWELL_KEYWORDS.
    """
    lowered = text.lower()
    return any(keyword in lowered for keyword in FAREWELL_KEYWORDS)


def extract_session_ending(response: str) -> bool:
    """Read the model's session_ending flag, whichever shape the turn used.

    Two response shapes are in play, so both are checked and OR'd together:

    - Primary: the whole response is one JSON object (the
      response_format=json_object contract) with "session_ending" at the top
      level.
    - Fallback: the current prompt asks for prose plus a trailing ```json
      fenced block (the same block extract_feedback reads "corrections"
      from); "session_ending" is read from that block instead.

    Mirrors parse_response's JSON handling but stays a separate function so
    parse_response's existing (reply, corrections) return shape — and every
    caller relying on it — is untouched; this is purely additive. Missing
    field, non-boolean value, malformed JSON, or no fenced block at all just
    mean False — this signal is advisory, not authoritative, so it must never
    raise.
    """
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, dict) and bool(data.get("session_ending", False)):
        return True

    fenced = _extract_fenced_json_block(response)
    if fenced is not None and bool(fenced.get("session_ending", False)):
        return True

    return False


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
