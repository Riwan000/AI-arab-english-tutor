"""Load prompt templates from YAML files."""

from functools import lru_cache
from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    path = _PROMPTS_DIR / name
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_system_prompt() -> str:
    return _load("system_prompt.yaml")["prompt"]


def get_lesson_context_template() -> str:
    return _load("lesson_context.yaml")["template"]


def get_start_message_template() -> str:
    return _load("start_conversation.yaml")["user_message"]
