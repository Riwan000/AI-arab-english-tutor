"""OpenRouter API client for LLM conversations."""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openai/gpt-4.1")


def chat_completion(messages: list[dict], model: str | None = None) -> str:
    if not OPENROUTER_API_KEY:
        return (
            "⚠️ OpenRouter API key not configured. "
            "Copy `.env.example` to `.env` and add your key."
        )

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
