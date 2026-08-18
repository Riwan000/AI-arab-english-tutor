"""OpenRouter API client for LLM conversations."""

import json
import os
from collections.abc import Iterator

import httpx
from dotenv import load_dotenv

from services.errors import LLMError, LLMRateLimitError, LLMTimeoutError

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openai/gpt-4.1")


def chat_completion_stream(messages: list[dict], model: str | None = None) -> Iterator[str]:
    """Call the LLM and yield raw response-text deltas as OpenRouter
    generates them (SSE) instead of blocking for the full completion. Lets a
    caller (services.conversation) start acting on the leading part of the
    reply — e.g. warming up speech synthesis — before the model has finished
    writing the rest. `"".join(chat_completion_stream(messages))` gives the
    same full JSON text a non-streaming call would have returned."""
    if not OPENROUTER_API_KEY:
        raise LLMError("OpenRouter API key not configured. Add OPENROUTER_API_KEY to .env")

    try:
        with httpx.stream(
            "POST",
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model or DEFAULT_MODEL,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "stream": True,
            },
            timeout=30.0,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = payload.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta
    except httpx.TimeoutException:
        raise LLMTimeoutError()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise LLMRateLimitError()
        raise LLMError(f"LLM API error: {exc.response.status_code}")
    except httpx.RequestError:
        raise LLMError("Could not reach LLM provider")
