"""OpenRouter API client for LLM conversations."""

import os

import httpx
from dotenv import load_dotenv

from services.errors import LLMError, LLMRateLimitError, LLMTimeoutError

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openai/gpt-4.1")


def chat_completion(messages: list[dict], model: str | None = None) -> str:
    if not OPENROUTER_API_KEY:
        raise LLMError("OpenRouter API key not configured. Add OPENROUTER_API_KEY to .env")

    try:
        response = httpx.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model or DEFAULT_MODEL,
                "messages": messages,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        raise LLMTimeoutError()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise LLMRateLimitError()
        raise LLMError(f"LLM API error: {exc.response.status_code}")
    except httpx.RequestError:
        raise LLMError("Could not reach LLM provider")
