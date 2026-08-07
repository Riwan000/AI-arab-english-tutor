# Backend Design Plan
# AI English Tutor for Arabic Speakers — Phase 1 MVP

**Version:** 1.0  
**Status:** Planned  
**References:** [prd.md](prd.md) · [hld.md](hld.md) · [db.md](db.md) · [tech-stack.md](tech-stack.md)

---

# 1. Overview

Phase 1 adopts a **split architecture**: a **FastAPI backend** owns all business logic, LLM calls, and database access; a **Streamlit frontend** on Streamlit Cloud handles UI only and communicates with the API over HTTP.

### Confirmed decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Backend framework | **FastAPI** |
| 2 | Chat loss on refresh | **Acceptable** — no server-side session store for active chat |
| 3 | Orchestration refactor | **Yes** — move chat logic to `services/conversation.py` |
| 4 | Deployment | **Demo on Streamlit Cloud** (frontend) + separate API host |
| 5 | Error handling | **Required for MVP** |
| 6 | JSON in chat display | **Strip** corrections JSON from visible AI reply |
| 7 | Database access | **Repository layer** over SQLite |
| 8 | Frontend host | **Streamlit Cloud** |

### Design goals

- Hide `OPENROUTER_API_KEY` on the API server only — never in Streamlit secrets
- Keep `services/` logic reusable by both FastAPI routes and (temporarily) Streamlit during migration
- Stateless chat API: client sends full message history on each request
- Completed sessions persisted to SQLite via repository layer (per [db.md](db.md))

---

# 2. Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Streamlit Cloud                                  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Streamlit App (UI only)                                          │  │
│  │  components/  →  api_client.py  →  HTTP                         │  │
│  └───────────────────────────────────┬───────────────────────────────┘  │
└──────────────────────────────────────┼──────────────────────────────────┘
                                       │ HTTPS
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Render / Railway / Fly.io)           │
│                                                                          │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────────────┐  │
│  │  api/routes │───►│    services/     │───►│   repositories/        │  │
│  │  lessons    │    │  conversation    │    │   session_repo         │  │
│  │  chat       │    │  openrouter      │    │   (SQLite)             │  │
│  │  sessions   │    │  grammar         │    └────────────────────────┘  │
│  └─────────────┘    │  scoring         │              │                 │
│                     │  lessons         │              ▼                 │
│                     └────────┬─────────┘    database/english_tutor.db    │
│                              │                                          │
│                              ▼                                          │
│                     ┌──────────────────┐                                │
│                     │   OpenRouter API  │                                │
│                     └──────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### Request flow (send message)

```
User types in Streamlit
    │
    ▼
api_client.send_message(lesson_id, messages, user_text)
    │
    ▼
POST /api/v1/chat/message
    │
    ▼
routes/chat.py
    │
    ▼
services/conversation.send_message()
    ├── prompts/prompt_builder.build_messages()
    ├── services/openrouter.chat_completion()
    ├── services/grammar.extract_feedback()
    ├── services/grammar.strip_json_from_response()   ← NEW
    └── return { reply, corrections }
    │
    ▼
Streamlit renders reply + correction_card
```

---

# 3. Deployment Architecture

Streamlit Cloud runs **only** the Streamlit app. FastAPI must be hosted separately.

### Recommended demo stack

| Component | Host | Cost (demo) | Notes |
|-----------|------|-------------|-------|
| Frontend | [Streamlit Cloud](https://streamlit.io/cloud) | Free | Connects to GitHub repo, `app.py` entry |
| Backend API | [Render](https://render.com) or [Railway](https://railway.app) | Free tier | Dockerfile or `uvicorn` start command |
| Database | SQLite on API server disk | Free | Ephemeral on free tier — acceptable for demo |
| LLM | OpenRouter | Pay-per-use | API key on backend only |

### Environment variables

**FastAPI server (`.env` on Render/Railway):**

```env
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DEFAULT_MODEL=openai/gpt-4.1
DATABASE_PATH=/app/database/english_tutor.db
CORS_ORIGINS=https://your-app.streamlit.app
API_HOST=0.0.0.0
API_PORT=8000
RETENTION_DAYS=5
```

**Streamlit Cloud (Secrets in dashboard):**

```toml
BACKEND_URL = "https://your-api.onrender.com"
```

> **No OpenRouter key in Streamlit.** The frontend never touches the LLM directly.

### CORS

FastAPI must allow requests from the Streamlit Cloud origin:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Streamlit Cloud URL
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### Streamlit Cloud limitation

SQLite on a free Render/Railway instance is **ephemeral** — data may reset on redeploy. Acceptable for demo. Note this in docs; migrate to PostgreSQL for production.

---

# 4. Project Structure (Target)

```
AI-arab-english-tutor/
│
├── app.py                          # Streamlit entry (UI only)
├── api_client.py                   # NEW — HTTP client for FastAPI
│
├── api/                            # NEW — FastAPI application
│   ├── __init__.py
│   ├── main.py                     # FastAPI app, CORS, lifespan
│   ├── config.py                   # Settings from env
│   ├── dependencies.py             # Shared deps (DB session, etc.)
│   ├── schemas/                    # Request/response Pydantic models
│   │   ├── __init__.py
│   │   ├── lesson.py
│   │   ├── chat.py
│   │   └── session.py
│   └── routes/
│       ├── __init__.py
│       ├── health.py
│       ├── lessons.py
│       ├── chat.py
│       └── sessions.py
│
├── components/                     # Streamlit UI (thin — calls api_client)
│   ├── chat.py
│   ├── sidebar.py
│   ├── lesson_view.py
│   ├── correction_card.py
│   └── summary.py
│
├── services/                       # Business logic (no HTTP, no UI)
│   ├── conversation.py             # NEW — chat orchestration
│   ├── lessons.py                  # NEW — load/cache lesson JSON
│   ├── openrouter.py               # LLM client + error handling
│   ├── grammar.py                  # Parse + strip JSON
│   ├── scoring.py                  # Session scoring
│   └── errors.py                   # NEW — custom exceptions
│
├── repositories/                   # NEW — data access layer
│   ├── __init__.py
│   └── session_repo.py             # CRUD for conversations/messages/feedback
│
├── prompts/
│   ├── system_prompt.py
│   └── prompt_builder.py
│
├── models/                         # Domain models (shared)
│   ├── lesson.py
│   ├── conversation.py
│   └── feedback.py
│
├── lessons/                        # Static JSON (served by API)
├── database/
│   └── english_tutor.db
│
├── Dockerfile                      # NEW — for API deployment
├── requirements.txt                # Updated with fastapi, uvicorn
├── requirements-api.txt            # NEW — API-only deps (optional split)
│
├── backend.md                      # This file
├── db.md
├── hld.md
└── ...
```

---

# 5. API Design

Base URL: `https://your-api.onrender.com/api/v1`

## 5.1 Health

### `GET /api/v1/health`

```json
{
  "status": "ok",
  "version": "1.0.0",
  "model": "openai/gpt-4.1"
}
```

Used by Streamlit on startup to verify backend connectivity.

---

## 5.2 Lessons

### `GET /api/v1/lessons`

List all available lessons.

**Response `200`:**
```json
{
  "lessons": [
    {
      "id": "present_simple",
      "title": "Present Simple",
      "description": "We use Present Simple for routines..."
    }
  ]
}
```

### `GET /api/v1/lessons/{lesson_id}`

Full lesson detail for the lesson viewer.

**Response `200`:**
```json
{
  "id": "present_simple",
  "title": "Present Simple",
  "description": "...",
  "examples": ["I eat breakfast every morning."],
  "grammar_rules": ["Use base verb form for I/you/we/they"],
  "allowed_vocabulary": ["eat", "work", "live"],
  "negative_form": ["I don't drink coffee."],
  "question_form": ["Do you work?"],
  "tips": ["Remember: he/she/it needs -s on the verb."]
}
```

**Response `404`:**
```json
{ "detail": "Lesson not found" }
```

---

## 5.3 Chat

Stateless — client sends full message history each time. No server-side chat session.

### `POST /api/v1/chat/start`

Generate the AI's opening message for a lesson.

**Request:**
```json
{
  "lesson_id": "present_simple"
}
```

**Response `200`:**
```json
{
  "reply": "Hello! Let's practice Present Simple. Tell me about your daily routine.",
  "corrections": []
}
```

---

### `POST /api/v1/chat/message`

Send a user message and receive AI reply + corrections.

**Request:**
```json
{
  "lesson_id": "present_simple",
  "messages": [
    {
      "role": "assistant",
      "content": "Tell me about your daily routine."
    },
    {
      "role": "user",
      "content": "I eating breakfast every morning."
    }
  ]
}
```

**Response `200`:**
```json
{
  "reply": "Almost! I eat breakfast every morning. Great try! Now, where do you work?",
  "corrections": [
    {
      "mistake_type": "Verb Form",
      "wrong_text": "I eating",
      "correct_text": "I eat",
      "english_explanation": "Present Simple uses the base verb.",
      "arabic_explanation": "في المضارع البسيط نستخدم الفعل بصيغته الأساسية.",
      "tip": "Try another sentence using 'eat'."
    }
  ]
}
```

> `reply` is **clean text only** — JSON correction block stripped server-side.

**Response `502` (LLM failure):**
```json
{
  "detail": "The AI tutor is temporarily unavailable. Please try again."
}
```

**Response `422`:** Validation error (missing lesson_id, empty messages, etc.)

---

## 5.4 Sessions

### `POST /api/v1/sessions`

Save a completed session (called on End Session / Start New Session).

**Request:**
```json
{
  "lesson_id": "present_simple",
  "messages": [
    {
      "role": "assistant",
      "content": "Tell me about your routine.",
      "timestamp": "2026-08-07T01:00:00+00:00"
    },
    {
      "role": "user",
      "content": "I eat breakfast every morning.",
      "timestamp": "2026-08-07T01:01:00+00:00"
    }
  ],
  "mistakes": [
    {
      "mistake_type": "Verb Form",
      "wrong_text": "I eating",
      "correct_text": "I eat",
      "english_explanation": "...",
      "arabic_explanation": "...",
      "tip": "...",
      "message_index": 1
    }
  ]
}
```

**Response `201`:**
```json
{
  "id": 42,
  "grammar_score": 90,
  "exchange_count": 5,
  "mistake_count": 1,
  "vocabulary": ["Breakfast", "Office"],
  "recommendation": "Excellent work! Try a harder lesson next.",
  "mistake_types": ["Verb Form"]
}
```

Backend calculates summary via `scoring.py` before saving.

---

### `GET /api/v1/sessions`

List past sessions (for sidebar).

**Query params:** `limit` (default 10, max 50)

**Response `200`:**
```json
{
  "sessions": [
    {
      "id": 42,
      "lesson_id": "present_simple",
      "lesson_title": "Present Simple",
      "ended_at": "2026-08-07T01:30:00+00:00",
      "grammar_score": 90,
      "exchange_count": 5,
      "mistake_count": 1,
      "recommendation": "..."
    }
  ]
}
```

---

### `GET /api/v1/sessions/{session_id}`

Full session summary for expander detail view.

**Response `200`:**
```json
{
  "id": 42,
  "lesson_id": "present_simple",
  "lesson_title": "Present Simple",
  "grammar_score": 90,
  "exchange_count": 5,
  "mistake_count": 1,
  "vocabulary": ["Breakfast", "Office"],
  "recommendation": "...",
  "mistake_types": [
    { "mistake_type": "Verb Form", "count": 1 }
  ]
}
```

---

# 6. Service Layer

## 6.1 `services/conversation.py` (NEW)

Central orchestration — no HTTP, no UI, no direct DB access.

```python
def start_conversation(lesson_id: str) -> ChatResponse:
    """Load lesson, build start prompt, call LLM, return clean reply."""

def send_message(lesson_id: str, messages: list[Message], user_text: str) -> ChatResponse:
    """Append user message, call LLM, parse corrections, return clean reply."""

def end_session(lesson_id: str, messages: list, mistakes: list) -> SessionSummary:
    """Score session, persist via repository, return summary."""
```

**`ChatResponse` model:**
```python
class ChatResponse(BaseModel):
    reply: str                          # clean text, no JSON block
    corrections: list[GrammarFeedback]  # empty if no mistakes
```

### Internal flow for `send_message`

```
1. lessons.get_lesson(lesson_id)           → raise LessonNotFoundError if missing
2. Append user message to history
3. prompt_builder.build_messages(lesson, history)
4. openrouter.chat_completion(messages)    → raw LLM text
5. grammar.extract_feedback(raw)           → list[GrammarFeedback]
6. grammar.strip_json_from_response(raw)   → clean reply text
7. Return ChatResponse(reply=clean, corrections=feedback)
```

---

## 6.2 `services/lessons.py` (NEW)

```python
def list_lessons() -> list[LessonSummary]: ...
def get_lesson(lesson_id: str) -> Lesson: ...   # raises LessonNotFoundError
```

- Loads from `lessons/*.json`
- Caches in memory after first load (lessons are static)
- Used by both API routes and conversation service

---

## 6.3 `services/grammar.py` (UPDATED)

Add JSON stripping:

```python
def extract_feedback(response: str) -> list[GrammarFeedback]:
    """Parse ```json {...} ``` block from LLM response."""

def strip_json_from_response(response: str) -> str:
    """Remove JSON correction block from visible reply text."""
```

**Strip logic:**
```python
import re

JSON_BLOCK_PATTERN = re.compile(r"```json\s*\{.*?\}\s*```", re.DOTALL)

def strip_json_from_response(response: str) -> str:
    cleaned = JSON_BLOCK_PATTERN.sub("", response).strip()
    return cleaned
```

---

## 6.4 `services/openrouter.py` (UPDATED)

Wrap HTTP calls with proper error handling:

```python
class LLMError(Exception): ...
class LLMTimeoutError(LLMError): ...
class LLMRateLimitError(LLMError): ...

def chat_completion(messages: list[dict], model: str | None = None) -> str:
    try:
        response = httpx.post(..., timeout=30.0)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        raise LLMTimeoutError("LLM request timed out")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise LLMRateLimitError("Rate limit exceeded")
        raise LLMError(f"LLM API error: {e.response.status_code}")
    except httpx.RequestError:
        raise LLMError("Could not reach LLM provider")
```

FastAPI routes catch these and return `502` with friendly message.

---

## 6.5 `services/errors.py` (NEW)

```python
class AppError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"

class LessonNotFoundError(AppError):
    status_code = 404
    detail = "Lesson not found"

class LLMError(AppError):
    status_code = 502
    detail = "The AI tutor is temporarily unavailable. Please try again."

class LLMTimeoutError(LLMError):
    detail = "The AI tutor took too long to respond. Please try again."

class LLMRateLimitError(LLMError):
    detail = "Too many requests. Please wait a moment and try again."
```

Registered in `api/main.py` as exception handlers.

---

## 6.6 `services/scoring.py`

No major changes. Called by `conversation.end_session()` before repository save.

---

# 7. Repository Layer

## 7.1 `repositories/session_repo.py` (NEW)

Thin data access over SQLite. Replaces direct calls from components to `database.py`.

```python
class SessionRepository:
    def save(
        self,
        lesson: Lesson,
        messages: list[dict],
        mistakes: list,
        summary: dict,
        model_used: str,
    ) -> int: ...

    def list_recent(self, limit: int = 10) -> list[dict]: ...

    def get_summary(self, conversation_id: int) -> dict | None: ...

    def purge_old(self, retention_days: int = 5) -> int: ...
```

Internally delegates to `database.py` connection logic (or absorbs it entirely).

### Migration path

```
Before:  components/summary.py  →  services/database.py
After:   api/routes/sessions.py  →  services/conversation.py  →  repositories/session_repo.py
         components/summary.py  →  api_client.py  →  api/routes/sessions.py
```

`services/database.py` becomes the low-level connection/schema module; `session_repo.py` is the public data access interface.

---

# 8. Streamlit Client Layer

## 8.1 `api_client.py` (NEW)

HTTP wrapper used by all Streamlit components. Reads `BACKEND_URL` from Streamlit secrets.

```python
import streamlit as st
import httpx

def _base_url() -> str:
    return st.secrets.get("BACKEND_URL", "http://localhost:8000")

def health_check() -> bool: ...

def list_lessons() -> list[dict]: ...

def get_lesson(lesson_id: str) -> dict: ...

def start_chat(lesson_id: str) -> dict: ...

def send_message(lesson_id: str, messages: list, user_text: str) -> dict: ...

def save_session(lesson_id: str, messages: list, mistakes: list) -> dict: ...

def list_sessions(limit: int = 10) -> list[dict]: ...

def get_session(session_id: int) -> dict: ...
```

### Error handling in client

```python
def send_message(...) -> dict:
    try:
        response = httpx.post(f"{_base_url()}/api/v1/chat/message", json=payload, timeout=35.0)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        st.error("The tutor took too long to respond. Please try again.")
        return {"reply": "", "corrections": []}
    except httpx.HTTPStatusError:
        st.error("The AI tutor is temporarily unavailable.")
        return {"reply": "", "corrections": []}
```

---

## 8.2 Component changes

| Component | Before | After |
|-----------|--------|-------|
| `sidebar.py` | `load_lessons()` from disk | `api_client.list_lessons()` |
| `sidebar.py` | `list_past_sessions()` direct DB | `api_client.list_sessions()` |
| `lesson_view.py` | Reads from session state | `api_client.get_lesson()` |
| `chat.py` | Direct `openrouter` + `grammar` | `api_client.start_chat()` / `send_message()` |
| `summary.py` | `persist_session()` direct DB | `api_client.save_session()` |
| `app.py` | `purge_old_conversations()` | Removed — backend handles on startup |

### `chat.py` after refactor (thin)

```python
def _handle_user_message(user_text: str, lesson: dict) -> None:
    st.session_state.messages.append({...})

    result = api_client.send_message(
        lesson_id=lesson["id"],
        messages=st.session_state.messages[:-1],  # history before current
        user_text=user_text,
    )

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["reply"],       # already stripped
        "feedback": result["corrections"],
        ...
    })
```

---

# 9. FastAPI Application

## 9.1 `api/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.routes import health, lessons, chat, sessions
from services.errors import AppError

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Purge old sessions on startup
    from repositories.session_repo import SessionRepository
    SessionRepository().purge_old(settings.retention_days)
    yield

app = FastAPI(title="AI English Tutor API", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, ...)

app.include_router(health.router, prefix="/api/v1")
app.include_router(lessons.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")

@app.exception_handler(AppError)
async def app_error_handler(request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
```

## 9.2 `api/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "openai/gpt-4.1"
    database_path: str = "database/english_tutor.db"
    cors_origins: list[str] = ["http://localhost:8501"]
    retention_days: int = 5

    class Config:
        env_file = ".env"
```

## 9.3 Local development

Run both processes:

```bash
# Terminal 1 — API
uvicorn api.main:app --reload --port 8000

# Terminal 2 — Streamlit
BACKEND_URL=http://localhost:8000 streamlit run app.py
```

Or use `.streamlit/secrets.toml` locally:

```toml
BACKEND_URL = "http://localhost:8000"
```

---

# 10. Error Handling Strategy

| Layer | Error | HTTP status | User sees |
|-------|-------|-------------|-----------|
| `openrouter.py` | Timeout | 502 | "Took too long to respond" |
| `openrouter.py` | 429 rate limit | 502 | "Too many requests" |
| `openrouter.py` | Other HTTP error | 502 | "Temporarily unavailable" |
| `openrouter.py` | Network failure | 502 | "Temporarily unavailable" |
| `lessons.py` | Lesson not found | 404 | "Lesson not found" |
| `grammar.py` | Malformed JSON | — | Empty corrections, show raw reply |
| FastAPI | Validation error | 422 | Field-level detail |
| `api_client.py` | Any HTTP error | — | Streamlit `st.error()` banner |

### Malformed JSON fallback

If LLM returns invalid JSON block:
- `extract_feedback()` returns `[]`
- `strip_json_from_response()` still removes the block if regex matches
- User sees conversational reply without corrections (graceful degradation)

---

# 11. Configuration & Secrets

| Secret | Where | Used by |
|--------|-------|---------|
| `OPENROUTER_API_KEY` | API server env | `services/openrouter.py` |
| `DEFAULT_MODEL` | API server env | `services/openrouter.py` |
| `CORS_ORIGINS` | API server env | `api/main.py` |
| `DATABASE_PATH` | API server env | `repositories/session_repo.py` |
| `RETENTION_DAYS` | API server env | API lifespan |
| `BACKEND_URL` | Streamlit Cloud secrets | `api_client.py` |

**Never commit:** `.env`, `.streamlit/secrets.toml`, API keys.

---

# 12. Dependencies

Add to `requirements.txt`:

```
# Existing
streamlit>=1.32.0
httpx>=0.27.0
python-dotenv>=1.0.0
pydantic>=2.6.0

# New — API
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
pydantic-settings>=2.2.0
```

---

# 13. Dockerfile (API deployment)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p database

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Deploy to Render/Railway with:
- **Build:** Docker
- **Health check path:** `/api/v1/health`
- **Persistent disk (optional):** mount `/app/database` for SQLite survival across redeploys

---

# 14. Implementation Phases

## Phase 1 — Service refactor (no API yet)

| Task | Files | Priority |
|------|-------|----------|
| Create `services/errors.py` | new | High |
| Create `services/lessons.py` | new | High |
| Add `strip_json_from_response()` | `services/grammar.py` | High |
| Add error handling | `services/openrouter.py` | High |
| Create `services/conversation.py` | new | High |
| Create `repositories/session_repo.py` | new | High |
| Refactor `database.py` as low-level module | update | Medium |
| Wire `chat.py` to `conversation.py` (in-process) | update | High |
| Verify JSON stripping in UI | test | High |

**Done when:** Streamlit works with refactored services, JSON stripped, errors handled — still no HTTP.

---

## Phase 2 — FastAPI layer

| Task | Files | Priority |
|------|-------|----------|
| Create `api/config.py` | new | High |
| Create `api/schemas/` | new | High |
| Create `api/routes/health.py` | new | High |
| Create `api/routes/lessons.py` | new | High |
| Create `api/routes/chat.py` | new | High |
| Create `api/routes/sessions.py` | new | High |
| Create `api/main.py` with CORS + error handlers | new | High |
| Create `api_client.py` | new | High |
| Refactor components to use `api_client` | update all components | High |
| Remove direct service imports from components | cleanup | High |
| Add Dockerfile | new | Medium |
| Update `.env.example` | update | Medium |

**Done when:** Streamlit talks to FastAPI over HTTP locally; all features work end-to-end.

---

## Phase 3 — Deploy

| Task | Priority |
|------|----------|
| Deploy FastAPI to Render/Railway | High |
| Set env vars on API host | High |
| Deploy Streamlit to Streamlit Cloud | High |
| Set `BACKEND_URL` in Streamlit secrets | High |
| Set `CORS_ORIGINS` to Streamlit Cloud URL on API | High |
| Smoke test: lesson → chat → correction → save → past sessions | High |
| Document deploy steps in README | Medium |

**Done when:** Public demo URL works end-to-end.

---

# 15. Testing Plan

| Test | Type | What to verify |
|------|------|----------------|
| `strip_json_from_response` | Unit | JSON block removed, text preserved |
| `extract_feedback` | Unit | Valid JSON parsed; invalid returns `[]` |
| `openrouter` error handling | Unit | Mock 429/timeout → correct exception |
| `conversation.send_message` | Unit | Full flow with mocked LLM |
| `session_repo.save` | Integration | Data written to SQLite correctly |
| `GET /lessons` | API | Returns all 5 lessons |
| `POST /chat/message` | API | Returns clean reply + corrections |
| `POST /sessions` | API | Saves and returns summary |
| End-to-end | Manual | Streamlit → API → OpenRouter → display |

---

# 16. Out of Scope (Phase 1 Backend)

- User authentication / JWT
- Server-side active chat sessions (Redis)
- WebSockets / streaming LLM responses
- Rate limiting per user
- PostgreSQL migration
- Admin API
- Background jobs (Celery)
- API versioning beyond `/api/v1`

---

# 17. Future Backend Evolution (Phase 2+)

| Enhancement | Trigger |
|-------------|---------|
| PostgreSQL | Multi-user production deploy |
| JWT auth | User accounts in PRD Phase 2 |
| Redis session store | Chat must survive refresh |
| SSE streaming | Real-time typing effect for AI replies |
| API rate limiting | Public launch |
| Langfuse / OpenTelemetry | LLM cost and quality monitoring |
| Separate `requirements-api.txt` | If Streamlit and API deploy independently |

---

# 18. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-08-07 | FastAPI for Phase 1 | Clean separation; hides API key from Streamlit Cloud |
| 2026-08-07 | Stateless chat API | Simpler; refresh loss acceptable for demo |
| 2026-08-07 | Repository layer | Clean data access; ready for PostgreSQL swap |
| 2026-08-07 | Strip JSON server-side | UI never sees raw LLM structure |
| 2026-08-07 | Streamlit Cloud + Render | Free demo stack; API key on backend only |
| 2026-08-07 | SQLite on API server | Matches [db.md](db.md); acceptable for demo |

---

*Next step: implement Phase 1 (service refactor), then Phase 2 (FastAPI layer), then Phase 3 (deploy).*
