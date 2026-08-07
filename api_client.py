"""HTTP client for the FastAPI backend — used by Streamlit components."""

import httpx
import streamlit as st

DEFAULT_TIMEOUT = 10.0
CHAT_TIMEOUT = 35.0


def base_url() -> str:
    """Return BACKEND_URL from Streamlit secrets, with local default."""
    return st.secrets.get("BACKEND_URL", "http://localhost:8000").rstrip("/")


def _url(path: str) -> str:
    return f"{base_url()}{path}"


def _serialize_message(msg: dict) -> dict:
    """Strip UI-only fields before sending to the API."""
    out: dict = {"role": msg["role"], "content": msg["content"]}
    if msg.get("timestamp"):
        out["timestamp"] = msg["timestamp"]
    return out


def _serialize_mistake(mistake: dict | object) -> dict:
    if hasattr(mistake, "model_dump"):
        data = mistake.model_dump(exclude_none=True)
    else:
        data = dict(mistake)
    return {
        k: data[k]
        for k in (
            "mistake_type",
            "wrong_text",
            "correct_text",
            "english_explanation",
            "arabic_explanation",
            "tip",
            "message_index",
        )
        if k in data
    }


def health_check() -> bool:
    response = httpx.get(_url("/api/v1/health"), timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.json().get("status") == "ok"


def list_lessons() -> list[dict]:
    response = httpx.get(_url("/api/v1/lessons"), timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.json().get("lessons", [])


def get_lesson(lesson_id: str) -> dict:
    response = httpx.get(
        _url(f"/api/v1/lessons/{lesson_id}"),
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def start_chat(lesson_id: str) -> dict:
    response = httpx.post(
        _url("/api/v1/chat/start"),
        json={"lesson_id": lesson_id},
        timeout=CHAT_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def send_message(lesson_id: str, messages: list, user_text: str) -> dict:
    payload = {
        "lesson_id": lesson_id,
        "messages": [_serialize_message(m) for m in messages]
        + [{"role": "user", "content": user_text}],
    }
    response = httpx.post(
        _url("/api/v1/chat/message"),
        json=payload,
        timeout=CHAT_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def save_session(lesson_id: str, messages: list, mistakes: list) -> dict:
    response = httpx.post(
        _url("/api/v1/sessions"),
        json={
            "lesson_id": lesson_id,
            "messages": [_serialize_message(m) for m in messages],
            "mistakes": [_serialize_mistake(m) for m in mistakes],
        },
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def list_sessions(limit: int = 10) -> list[dict]:
    response = httpx.get(
        _url("/api/v1/sessions"),
        params={"limit": limit},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("sessions", [])


def get_session(session_id: int) -> dict:
    response = httpx.get(
        _url(f"/api/v1/sessions/{session_id}"),
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()
