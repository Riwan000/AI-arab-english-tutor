"""Parses grammar feedback from LLM responses."""

import json
import re

from models.feedback import GrammarFeedback


def extract_feedback(response: str) -> list[GrammarFeedback]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    corrections = data.get("corrections", [])
    return [GrammarFeedback(**item) for item in corrections]
