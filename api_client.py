"""HTTP client for the FastAPI backend — used by Streamlit components."""

import httpx
import streamlit as st

DEFAULT_TIMEOUT = 10.0
CHAT_TIMEOUT = 35.0
VOICE_TIMEOUT = 35.0

BACKEND_UNAVAILABLE = "Could not connect to the backend. Check BACKEND_URL and ensure the API is running."
CHAT_TIMEOUT_MESSAGE = "The tutor took too long to respond. Please try again."
REQUEST_TIMEOUT_MESSAGE = "The request took too long. Please try again."
VOICE_TIMEOUT_MESSAGE = "Voice processing took too long. Please try again."
LLM_UNAVAILABLE = "The AI tutor is temporarily unavailable. Please try again."

_auth_token: str | None = None


def set_auth_token(token: str | None) -> None:
    """Store the JWT in module state so subsequent requests send it as a Bearer header."""
    global _auth_token
    _auth_token = token


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_auth_token}"} if _auth_token else {}


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


def _response_detail(response: httpx.Response) -> str | dict | None:
    try:
        return response.json().get("detail")
    except Exception:
        return None


def _error_message(detail: str | dict | None) -> str:
    if isinstance(detail, dict):
        return str(detail.get("message") or LLM_UNAVAILABLE)
    return str(detail) if detail else LLM_UNAVAILABLE


def _is_daily_limit_detail(status_code: int, detail: str | dict | None) -> bool:
    """True for the text-message daily limit only.

    The voice-call limit (`kind: "voice"`) is a separate counter (services/usage.py)
    and must not disable st.chat_input — only the message limit does that.
    """
    return (
        status_code == 429
        and isinstance(detail, dict)
        and "remaining" in detail
        and detail.get("kind") != "voice"
    )


def _show_error(message: str) -> None:
    st.error(message)


def _handle_response_error(exc: httpx.HTTPStatusError) -> None:
    """Show the error, unless this is a stale session — then clear it for app.py to catch.

    A 401 only means "session expired" when we thought we had one (`_auth_token`
    was set). A 401 with no token set is a normal login/signup credential
    failure and must surface its own message instead.
    """
    if exc.response.status_code == 401 and _auth_token is not None:
        set_auth_token(None)
        st.session_state["force_logout"] = True
        return
    detail = _response_detail(exc.response)
    if _is_daily_limit_detail(exc.response.status_code, detail):
        st.session_state["daily_limit_reached"] = True
    _show_error(_error_message(detail))


def _request_get(
    path: str,
    *,
    params: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    fallback: object,
    timeout_message: str = REQUEST_TIMEOUT_MESSAGE,
) -> object:
    try:
        response = httpx.get(_url(path), params=params, timeout=timeout, headers=_auth_headers())
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        _show_error(timeout_message)
    except httpx.HTTPStatusError as exc:
        _handle_response_error(exc)
    except httpx.RequestError:
        _show_error(BACKEND_UNAVAILABLE)
    return fallback


def _request_post(
    path: str,
    *,
    json: dict,
    timeout: float = DEFAULT_TIMEOUT,
    fallback: object,
    timeout_message: str = REQUEST_TIMEOUT_MESSAGE,
) -> object:
    try:
        response = httpx.post(_url(path), json=json, timeout=timeout, headers=_auth_headers())
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        _show_error(timeout_message)
    except httpx.HTTPStatusError as exc:
        _handle_response_error(exc)
    except httpx.RequestError:
        _show_error(BACKEND_UNAVAILABLE)
    return fallback


def _request_post_multipart(
    path: str,
    *,
    files: dict,
    timeout: float = DEFAULT_TIMEOUT,
    fallback: object,
    timeout_message: str = REQUEST_TIMEOUT_MESSAGE,
) -> object:
    try:
        response = httpx.post(_url(path), files=files, timeout=timeout, headers=_auth_headers())
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        _show_error(timeout_message)
    except httpx.HTTPStatusError as exc:
        _handle_response_error(exc)
    except httpx.RequestError:
        _show_error(BACKEND_UNAVAILABLE)
    return fallback


def _request_post_raw(
    path: str,
    *,
    json: dict,
    timeout: float = DEFAULT_TIMEOUT,
    fallback: object,
    timeout_message: str = REQUEST_TIMEOUT_MESSAGE,
) -> object:
    """Like _request_post, but returns the raw response body bytes instead of parsed JSON."""
    try:
        response = httpx.post(_url(path), json=json, timeout=timeout, headers=_auth_headers())
        response.raise_for_status()
        return response.content
    except httpx.TimeoutException:
        _show_error(timeout_message)
    except httpx.HTTPStatusError as exc:
        _handle_response_error(exc)
    except httpx.RequestError:
        _show_error(BACKEND_UNAVAILABLE)
    return fallback


def health_check() -> bool:
    """Return True when the backend health endpoint responds ok (no UI error banner)."""
    try:
        response = httpx.get(_url("/api/v1/health"), timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json().get("status") == "ok"
    except (httpx.HTTPError, httpx.RequestError):
        return False


def signup(email: str, password: str, display_name: str) -> dict | None:
    data = _request_post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "display_name": display_name},
        fallback=None,
    )
    return data if isinstance(data, dict) else None


def login(email: str, password: str) -> dict | None:
    data = _request_post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        fallback=None,
    )
    return data if isinstance(data, dict) else None


def list_lessons() -> list[dict]:
    data = _request_get("/api/v1/lessons", fallback={})
    if isinstance(data, dict):
        return data.get("lessons", [])
    return []


def get_lesson(lesson_id: str) -> dict | None:
    data = _request_get(f"/api/v1/lessons/{lesson_id}", fallback=None)
    return data if isinstance(data, dict) else None


def start_chat(lesson_id: str | None, difficulty: str = "beginner", mode: str = "lesson") -> dict:
    data = _request_post(
        "/api/v1/chat/start",
        json={"lesson_id": lesson_id, "difficulty": difficulty, "mode": mode},
        timeout=CHAT_TIMEOUT,
        fallback={"reply": "", "corrections": []},
        timeout_message=CHAT_TIMEOUT_MESSAGE,
    )
    return data if isinstance(data, dict) else {"reply": "", "corrections": []}


def send_message(
    lesson_id: str | None,
    messages: list,
    user_text: str,
    difficulty: str = "beginner",
    mode: str = "lesson",
) -> dict:
    payload = {
        "lesson_id": lesson_id,
        "difficulty": difficulty,
        "mode": mode,
        "messages": [_serialize_message(m) for m in messages]
        + [{"role": "user", "content": user_text}],
    }
    data = _request_post(
        "/api/v1/chat/message",
        json=payload,
        timeout=CHAT_TIMEOUT,
        fallback={"reply": "", "corrections": []},
        timeout_message=CHAT_TIMEOUT_MESSAGE,
    )
    return data if isinstance(data, dict) else {"reply": "", "corrections": []}


def save_session(
    lesson_id: str | None,
    messages: list,
    mistakes: list,
    mode: str = "lesson",
) -> dict | None:
    data = _request_post(
        "/api/v1/sessions",
        json={
            "lesson_id": lesson_id,
            "mode": mode,
            "messages": [_serialize_message(m) for m in messages],
            "mistakes": [_serialize_mistake(m) for m in mistakes],
        },
        timeout=DEFAULT_TIMEOUT,
        fallback=None,
    )
    return data if isinstance(data, dict) else None


def list_sessions(limit: int = 10) -> list[dict]:
    data = _request_get(
        "/api/v1/sessions",
        params={"limit": limit},
        fallback={},
    )
    if isinstance(data, dict):
        return data.get("sessions", [])
    return []


def get_session(session_id: int) -> dict | None:
    data = _request_get(f"/api/v1/sessions/{session_id}", fallback=None)
    return data if isinstance(data, dict) else None


def get_usage_today() -> dict | None:
    data = _request_get("/api/v1/usage/today", fallback=None)
    return data if isinstance(data, dict) else None


def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/wav") -> str | None:
    data = _request_post_multipart(
        "/api/v1/voice/transcribe",
        files={"audio": ("audio", audio_bytes, mimetype)},
        timeout=VOICE_TIMEOUT,
        fallback=None,
        timeout_message=VOICE_TIMEOUT_MESSAGE,
    )
    return data.get("text") if isinstance(data, dict) else None


def synthesize_speech(text: str, language: str = "en") -> bytes | None:
    data = _request_post_raw(
        "/api/v1/voice/speak",
        json={"text": text, "language": language},
        timeout=VOICE_TIMEOUT,
        fallback=None,
        timeout_message=VOICE_TIMEOUT_MESSAGE,
    )
    return data if isinstance(data, bytes) else None
