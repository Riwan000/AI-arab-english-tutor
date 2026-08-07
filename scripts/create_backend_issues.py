"""One-time script to create backend.md implementation issues on GitHub."""
import json
import subprocess
import sys

REPO = "Riwan000/AI-arab-english-tutor"

ISSUES = [
    # Phase 0
    {
        "title": "[0.1] Verify domain models",
        "milestone": 1,
        "labels": ["phase-0", "priority-high", "type-foundation"],
        "body": """## Task
Ensure `Lesson`, `Message`, and `GrammarFeedback` models match API schemas in backend.md §5.

## Files
- `models/lesson.py`
- `models/conversation.py`
- `models/feedback.py`

## Acceptance criteria
- Models are usable by services and Pydantic API schemas
- Field names align with `db.md` and API request/response shapes

## Reference
backend.md — Phase 0, §5 API Design""",
    },
    {
        "title": "[0.2] Verify database.py schema and operations",
        "milestone": 1,
        "labels": ["phase-0", "priority-high", "type-foundation"],
        "body": """## Task
Confirm `services/database.py` implements schema v2 per db.md with save, list, get summary, and purge.

## Files
- `services/database.py`

## Acceptance criteria
- Schema v2 tables: conversations, messages, grammar_feedback
- `save_conversation`, `list_past_sessions`, `get_session_summary`, `purge_old` work standalone

## Reference
db.md — §3 Schema, §5 Write Path, §6 Read Path""",
    },
    {
        "title": "[0.3] Update requirements.txt with API dependencies",
        "milestone": 1,
        "labels": ["phase-0", "priority-high", "type-foundation"],
        "body": """## Task
Add FastAPI stack dependencies to requirements.

## Packages to add
- `fastapi>=0.110.0`
- `uvicorn[standard]>=0.27.0`
- `pydantic-settings>=2.2.0`

## Files
- `requirements.txt`

## Acceptance criteria
- `pip install -r requirements.txt` succeeds in a clean venv""",
    },
    {
        "title": "[0.4] Update .env.example with API environment variables",
        "milestone": 1,
        "labels": ["phase-0", "priority-medium", "type-foundation"],
        "body": """## Task
Document all backend environment variables in `.env.example`.

## Variables
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `DEFAULT_MODEL`
- `DATABASE_PATH`
- `CORS_ORIGINS`
- `RETENTION_DAYS`
- `API_HOST`, `API_PORT`

## Files
- `.env.example`

## Acceptance criteria
- Template matches backend.md §11 Configuration & Secrets""",
    },
    # Phase 1A — Errors
    {
        "title": "[1.1] Create services/errors.py",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-service"],
        "body": """## Task
Create custom exception hierarchy for the service and API layers.

## Classes
- `AppError` (base, status_code=500)
- `LessonNotFoundError` (404)
- `LLMError` (502)
- `LLMTimeoutError`
- `LLMRateLimitError`

## Files
- `services/errors.py` (new)

## Depends on
- #0.1 (domain models)

## Reference
backend.md — §6.5""",
    },
    {
        "title": "[1.2] Add error handling to services/openrouter.py",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-service"],
        "body": """## Task
Wrap httpx calls with proper exception mapping.

## Behavior
- `httpx.TimeoutException` → `LLMTimeoutError`
- HTTP 429 → `LLMRateLimitError`
- Other HTTP errors → `LLMError`
- Network failures → `LLMError`

## Files
- `services/openrouter.py`

## Depends on
- #1.1

## Reference
backend.md — §6.4""",
    },
    {
        "title": "[1.3] Remove fake API-key string fallback from openrouter",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-service"],
        "body": """## Task
Replace the current string fallback when API key is missing with proper error handling.

## Current behavior
Returns a warning string in chat when key is missing.

## Target behavior
Raise `LLMError` or validate config at startup.

## Files
- `services/openrouter.py`

## Depends on
- #1.2""",
    },
    # Phase 1B — Grammar & Lessons
    {
        "title": "[1.4] Add strip_json_from_response() to grammar service",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-service"],
        "body": """## Task
Strip JSON correction blocks from visible LLM reply text.

## Implementation
```python
JSON_BLOCK_PATTERN = re.compile(r"```json\\s*\\{.*?\\}\\s*```", re.DOTALL)
```

## Files
- `services/grammar.py`

## Acceptance criteria
- JSON block removed from reply
- Conversational text preserved

## Reference
backend.md — §6.3""",
    },
    {
        "title": "[1.5] Harden extract_feedback() malformed JSON handling",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-service"],
        "body": """## Task
Ensure malformed JSON in LLM response returns empty corrections gracefully.

## Behavior
- Valid JSON → `list[GrammarFeedback]`
- Invalid/missing JSON → `[]`

## Files
- `services/grammar.py`

## Depends on
- #1.4""",
    },
    {
        "title": "[1.6] Create services/lessons.py",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-service"],
        "body": """## Task
Create lesson loading service with in-memory cache.

## Functions
- `list_lessons() -> list[LessonSummary]`
- `get_lesson(lesson_id: str) -> Lesson` (raises `LessonNotFoundError`)

## Files
- `services/lessons.py` (new)

## Depends on
- #1.1, #0.1

## Reference
backend.md — §6.2""",
    },
    {
        "title": "[1.7] Load lessons from lessons/*.json with caching",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-service"],
        "body": """## Task
Load all 5 lesson JSON files and cache in memory after first load.

## Lessons
- present_simple, present_continuous, past_simple, articles, prepositions

## Files
- `services/lessons.py`
- `lessons/*.json`

## Depends on
- #1.6""",
    },
    # Phase 1C — Conversation
    {
        "title": "[1.8] Define ChatResponse model",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-service"],
        "body": """## Task
Define response model for conversation service.

## Model
```python
class ChatResponse(BaseModel):
    reply: str
    corrections: list[GrammarFeedback]
```

## Files
- `services/conversation.py` or `models/`

## Depends on
- #0.1""",
    },
    {
        "title": "[1.9] Implement start_conversation() in conversation service",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-service"],
        "body": """## Task
Implement AI opening message flow.

## Flow
1. Load lesson via `lessons.get_lesson()`
2. `prompt_builder.build_messages(..., start=True)` (loads templates from `prompts/*.yaml`)
3. `openrouter.chat_completion()`
4. `grammar.extract_feedback()` + `strip_json_from_response()`
5. Return `ChatResponse`

## Files
- `services/conversation.py` (new)
- `prompts/system_prompt.yaml`, `lesson_context.yaml`, `start_conversation.yaml`

## Depends on
- #1.6, #1.4, #1.2, #1.8""",
    },
    {
        "title": "[1.10] Implement send_message() in conversation service",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-service"],
        "body": """## Task
Implement stateless message handling orchestration.

## Flow
1. Validate lesson exists
2. Append user message to history
3. Build prompt from `prompts/*.yaml` via `prompt_builder` → LLM → parse → strip
4. Return `ChatResponse`

## Files
- `services/conversation.py`

## Depends on
- #1.9

## Reference
backend.md — §6.1 internal flow""",
    },
    {
        "title": "[1.11] Implement end_session() in conversation service",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-service"],
        "body": """## Task
Score session and persist via repository.

## Flow
1. Call `scoring.calculate_session_summary()`
2. Persist via `SessionRepository.save()`
3. Return session summary

## Files
- `services/conversation.py`

## Depends on
- #1.10, #1.12""",
    },
    # Phase 1D — Repository
    {
        "title": "[1.12] Create repositories/session_repo.py",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-repository"],
        "body": """## Task
Create repository layer over SQLite.

## Methods
- `save(lesson, messages, mistakes, summary, model_used) -> int`
- `list_recent(limit=10) -> list[dict]`
- `get_summary(conversation_id) -> dict | None`
- `purge_old(retention_days=5) -> int`

## Files
- `repositories/session_repo.py` (new)
- `repositories/__init__.py` (new)

## Depends on
- #0.2

## Reference
backend.md — §7.1""",
    },
    {
        "title": "[1.13] Refactor database.py as low-level connection module",
        "milestone": 2,
        "labels": ["phase-1", "priority-medium", "type-repository"],
        "body": """## Task
Clarify separation: `database.py` = connection/schema; `session_repo.py` = public data access.

## Files
- `services/database.py`
- `repositories/session_repo.py`

## Depends on
- #1.12""",
    },
    {
        "title": "[1.14] Map session save payload to database schema",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-repository"],
        "body": """## Task
Ensure repository save maps all fields per db.md.

## Mapping
- Lesson metadata, messages with timestamps, mistakes with message_index
- Scoring fields, vocabulary JSON, model_used

## Files
- `repositories/session_repo.py`

## Depends on
- #1.12

## Reference
db.md — §5.3""",
    },
    # Phase 1E — Wire Streamlit
    {
        "title": "[1.15] Refactor chat.py to use conversation service",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-ui"],
        "body": """## Task
Replace direct `openrouter` and `grammar` calls with `conversation` service.

## Files
- `components/chat.py`

## Depends on
- #1.10

## Before → After
- `chat_completion()` → `conversation.send_message()`
- `_start_conversation()` → `conversation.start_conversation()`""",
    },
    {
        "title": "[1.16] Store clean reply and corrections in chat state",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-ui"],
        "body": """## Task
Assistant message content must be stripped reply only.

## State shape
- `content` = clean `reply` (no JSON block)
- `feedback` = `corrections` list

## Files
- `components/chat.py`

## Depends on
- #1.15""",
    },
    {
        "title": "[1.17] Handle LLM errors in chat UI",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-ui"],
        "body": """## Task
Catch `LLMError` subclasses and show friendly Streamlit error banners.

## Files
- `components/chat.py`

## Depends on
- #1.15, #1.1""",
    },
    {
        "title": "[1.18] Refactor summary.py to use conversation.end_session()",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-ui"],
        "body": """## Task
Replace direct DB calls in `persist_session()` with conversation/repository layer.

## Files
- `components/summary.py`

## Depends on
- #1.11""",
    },
    {
        "title": "[1.19] Refactor sidebar.py to use lessons service",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-ui"],
        "body": """## Task
Replace disk `load_lessons()` with `lessons.list_lessons()`.

## Files
- `components/sidebar.py`

## Depends on
- #1.6""",
    },
    {
        "title": "[1.20] Wire sidebar past sessions via repository (temporary)",
        "milestone": 2,
        "labels": ["phase-1", "priority-medium", "type-ui"],
        "body": """## Task
Use `SessionRepository.list_recent()` in sidebar until Phase 2 HTTP migration.

## Files
- `components/sidebar.py`

## Depends on
- #1.12

## Note
Will switch to `api_client.list_sessions()` in Phase 2.""",
    },
    # Phase 1F — Verification
    {
        "title": "[1.21] Verify JSON stripping in chat UI",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-test"],
        "body": """## Task
Manual verification: chat bubbles must not show ```json blocks.

## Depends on
- #1.16""",
    },
    {
        "title": "[1.22] Verify correction cards still render",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-test"],
        "body": """## Task
Manual verification: `correction_card` renders from `feedback` on assistant messages.

## Depends on
- #1.16""",
    },
    {
        "title": "[1.23] Verify session save on End Session",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-test"],
        "body": """## Task
Manual verification: completed session writes to SQLite correctly.

## Depends on
- #1.18""",
    },
    {
        "title": "[1.24] Verify LLM error handling paths",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-test"],
        "body": """## Task
Test: invalid lesson, timeout, missing API key show user-friendly errors.

## Depends on
- #1.17""",
    },
    {
        "title": "[1.25] Phase 1 exit — full in-process flow works",
        "milestone": 2,
        "labels": ["phase-1", "priority-high", "type-test"],
        "body": """## Task
Phase 1 complete when Streamlit works with refactored services — no HTTP yet.

## Checklist
- [ ] JSON stripped from visible replies
- [ ] Errors handled gracefully
- [ ] Sessions persist to SQLite
- [ ] Past sessions appear in sidebar
- [ ] No direct openrouter/grammar imports in components

## Reference
backend.md — Phase 1 done criteria""",
    },
    # Phase 2A — API config
    {
        "title": "[2.1] Create api/config.py with Settings",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Pydantic Settings from environment variables.

## Settings
- openrouter_api_key, openrouter_base_url, default_model
- database_path, cors_origins, retention_days

## Files
- `api/config.py` (new)

## Depends on
- #0.3

## Reference
backend.md — §9.2""",
    },
    {
        "title": "[2.2] Create api/dependencies.py",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Shared FastAPI dependencies for DB session and repository injection.

## Files
- `api/dependencies.py` (new)

## Depends on
- #2.1, #1.12""",
    },
    {
        "title": "[2.3] Create api/main.py with CORS and lifespan",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
FastAPI app shell with CORS middleware and startup purge.

## Features
- Lifespan: purge old sessions on startup
- CORS for Streamlit origin
- Router registration

## Files
- `api/main.py` (new)
- `api/__init__.py` (new)

## Depends on
- #2.1

## Reference
backend.md — §9.1""",
    },
    {
        "title": "[2.4] Register AppError exception handlers in api/main.py",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Map `AppError` subclasses to JSON responses with correct status codes.

## Files
- `api/main.py`

## Depends on
- #2.3, #1.1""",
    },
    {
        "title": "[2.5] Remove purge from Streamlit app.py",
        "milestone": 3,
        "labels": ["phase-2", "priority-medium", "type-ui"],
        "body": """## Task
Backend owns retention purge on API startup; remove from Streamlit.

## Files
- `app.py`

## Depends on
- #2.3""",
    },
    # Phase 2B — Schemas
    {
        "title": "[2.6] Create api/schemas/lesson.py",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Pydantic schemas for lesson endpoints.

## Models
- LessonSummary, LessonDetail, LessonsListResponse

## Files
- `api/schemas/lesson.py` (new)
- `api/schemas/__init__.py` (new)

## Reference
backend.md — §5.2""",
    },
    {
        "title": "[2.7] Create api/schemas/chat.py",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Pydantic schemas for chat endpoints.

## Models
- ChatStartRequest, ChatMessageRequest, Message, ChatResponse, GrammarFeedback

## Files
- `api/schemas/chat.py` (new)

## Reference
backend.md — §5.3""",
    },
    {
        "title": "[2.8] Create api/schemas/session.py",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Pydantic schemas for session endpoints.

## Models
- SessionCreateRequest, SessionSummaryResponse, SessionListResponse, SessionDetailResponse

## Files
- `api/schemas/session.py` (new)

## Reference
backend.md — §5.4""",
    },
    # Phase 2C — Routes
    {
        "title": "[2.9] Create GET /api/v1/health route",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Health check endpoint for backend connectivity.

## Response
```json
{ "status": "ok", "version": "1.0.0", "model": "openai/gpt-4.1" }
```

## Files
- `api/routes/health.py` (new)
- `api/routes/__init__.py` (new)

## Reference
backend.md — §5.1""",
    },
    {
        "title": "[2.10] Create GET /api/v1/lessons route",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
List all available lessons.

## Files
- `api/routes/lessons.py` (new)

## Depends on
- #1.6, #2.6""",
    },
    {
        "title": "[2.11] Create GET /api/v1/lessons/{lesson_id} route",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Full lesson detail; 404 on unknown lesson.

## Files
- `api/routes/lessons.py`

## Depends on
- #2.10""",
    },
    {
        "title": "[2.12] Create POST /api/v1/chat/start route",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Generate AI opening message for a lesson.

## Request
`{ "lesson_id": "present_simple" }`

## Response
`{ "reply": "...", "corrections": [] }`

## Files
- `api/routes/chat.py` (new)

## Depends on
- #1.9, #2.7""",
    },
    {
        "title": "[2.13] Create POST /api/v1/chat/message route",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Stateless chat — client sends full history; returns clean reply + corrections.

## Errors
- 404 lesson not found
- 422 validation error
- 502 LLM failure

## Files
- `api/routes/chat.py`

## Depends on
- #1.10, #2.7""",
    },
    {
        "title": "[2.14] Create POST /api/v1/sessions route",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Save completed session; score via scoring.py; return 201 summary.

## Files
- `api/routes/sessions.py` (new)

## Depends on
- #1.11, #2.8""",
    },
    {
        "title": "[2.15] Create GET /api/v1/sessions route",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
List past sessions for sidebar. Query param `limit` (default 10, max 50).

## Files
- `api/routes/sessions.py`

## Depends on
- #1.12, #2.8""",
    },
    {
        "title": "[2.16] Create GET /api/v1/sessions/{session_id} route",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-api"],
        "body": """## Task
Full session summary with mistake type breakdown.

## Files
- `api/routes/sessions.py`

## Depends on
- #2.15""",
    },
    # Phase 2D — api_client
    {
        "title": "[2.17] Create api_client.py with base URL helper",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-ui"],
        "body": """## Task
HTTP client for Streamlit; reads `BACKEND_URL` from secrets.

## Files
- `api_client.py` (new)

## Reference
backend.md — §8.1""",
    },
    {
        "title": "[2.18] Implement all api_client HTTP methods",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-ui"],
        "body": """## Task
Implement client methods for all API endpoints.

## Methods
- health_check, list_lessons, get_lesson
- start_chat, send_message
- save_session, list_sessions, get_session

## Files
- `api_client.py`

## Depends on
- #2.17, #2.9–#2.16""",
    },
    {
        "title": "[2.19] Add error handling to api_client.py",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-ui"],
        "body": """## Task
Timeout and HTTP errors → `st.error()` with friendly messages and safe fallbacks.

## Files
- `api_client.py`

## Depends on
- #2.18""",
    },
    {
        "title": "[2.20] Add backend health check on Streamlit startup",
        "milestone": 3,
        "labels": ["phase-2", "priority-medium", "type-ui"],
        "body": """## Task
Verify backend connectivity when app loads.

## Files
- `app.py`

## Depends on
- #2.18""",
    },
    # Phase 2E — Component HTTP migration
    {
        "title": "[2.21] Migrate sidebar.py to api_client",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-ui"],
        "body": """## Task
- `api_client.list_lessons()`
- `api_client.list_sessions()`

## Files
- `components/sidebar.py""",
    },
    {
        "title": "[2.22] Migrate lesson_view.py to api_client",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-ui"],
        "body": """## Task
Fetch lesson detail via `api_client.get_lesson()`.

## Files
- `components/lesson_view.py`""",
    },
    {
        "title": "[2.23] Migrate chat.py to api_client",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-ui"],
        "body": """## Task
- `api_client.start_chat()`
- `api_client.send_message()`

## Files
- `components/chat.py`""",
    },
    {
        "title": "[2.24] Migrate summary.py to api_client",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-ui"],
        "body": """## Task
`api_client.save_session()` instead of direct DB/service calls.

## Files
- `components/summary.py`""",
    },
    {
        "title": "[2.25] Remove direct service imports from all components",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-ui"],
        "body": """## Task
Components must only call `api_client` — no openrouter, grammar, database, or conversation imports.

## Files
- `components/*.py`
- `app.py`""",
    },
    {
        "title": "[2.26] Remove OPENROUTER_API_KEY from Streamlit config",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-ui"],
        "body": """## Task
Frontend only needs `BACKEND_URL` in Streamlit secrets.

## Files
- `app.py`
- `.streamlit/secrets.toml` (local example)""",
    },
    # Phase 2F — Deploy artifacts
    {
        "title": "[2.27] Create Dockerfile for API deployment",
        "milestone": 3,
        "labels": ["phase-2", "priority-medium", "type-deploy"],
        "body": """## Task
Python 3.11-slim image with uvicorn entrypoint.

## Files
- `Dockerfile` (new)

## Reference
backend.md — §13""",
    },
    {
        "title": "[2.28] Create optional requirements-api.txt",
        "milestone": 3,
        "labels": ["phase-2", "priority-medium", "type-deploy"],
        "body": """## Task
Optional split of API-only dependencies if Streamlit and API deploy separately.

## Files
- `requirements-api.txt` (optional)""",
    },
    {
        "title": "[2.29] Document local two-process dev setup in README",
        "milestone": 3,
        "labels": ["phase-2", "priority-medium", "type-deploy"],
        "body": """## Task
Document running uvicorn + streamlit locally.

```bash
uvicorn api.main:app --reload --port 8000
streamlit run app.py  # with BACKEND_URL=http://localhost:8000
```

## Files
- `README.md`""",
    },
    # Phase 2G — Verification
    {
        "title": "[2.30] Verify GET /api/v1/health returns 200",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-test"],
        "body": """## Task
API smoke test: health endpoint.""",
    },
    {
        "title": "[2.31] Verify GET /api/v1/lessons returns 5 lessons",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-test"],
        "body": """## Task
API smoke test: lessons list.""",
    },
    {
        "title": "[2.32] Verify POST /chat/message returns clean reply + corrections",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-test"],
        "body": """## Task
API smoke test: chat message endpoint.""",
    },
    {
        "title": "[2.33] Verify POST /sessions saves and returns summary",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-test"],
        "body": """## Task
API smoke test: session save endpoint.""",
    },
    {
        "title": "[2.34] Phase 2 exit — Streamlit E2E over HTTP",
        "milestone": 3,
        "labels": ["phase-2", "priority-high", "type-test"],
        "body": """## Task
Phase 2 complete when full flow works locally over HTTP.

## Checklist
- [ ] uvicorn + streamlit run together
- [ ] lesson → chat → correction → end session → past sessions
- [ ] No OpenRouter key in Streamlit

## Reference
backend.md — Phase 2 done criteria""",
    },
    # Phase 3 — Deploy
    {
        "title": "[3.1] Deploy FastAPI to Render or Railway",
        "milestone": 4,
        "labels": ["phase-3", "priority-high", "type-deploy"],
        "body": """## Task
Deploy API with Docker or uvicorn start command.

## Health check
`/api/v1/health`

## Reference
backend.md — §3 Deployment Architecture""",
    },
    {
        "title": "[3.2] Set API environment variables on host",
        "milestone": 4,
        "labels": ["phase-3", "priority-high", "type-deploy"],
        "body": """## Task
Configure on Render/Railway:
- OPENROUTER_API_KEY, OPENROUTER_BASE_URL, DEFAULT_MODEL
- DATABASE_PATH, CORS_ORIGINS, RETENTION_DAYS""",
    },
    {
        "title": "[3.3] Configure optional persistent disk for SQLite",
        "milestone": 4,
        "labels": ["phase-3", "priority-medium", "type-deploy"],
        "body": """## Task
Mount `/app/database` on API host so SQLite survives redeploys (optional for demo).""",
    },
    {
        "title": "[3.4] Deploy Streamlit app to Streamlit Cloud",
        "milestone": 4,
        "labels": ["phase-3", "priority-high", "type-deploy"],
        "body": """## Task
Connect GitHub repo; entry point `app.py`.""",
    },
    {
        "title": "[3.5] Set BACKEND_URL in Streamlit Cloud secrets",
        "milestone": 4,
        "labels": ["phase-3", "priority-high", "type-deploy"],
        "body": """## Task
```toml
BACKEND_URL = "https://your-api.onrender.com"
```

No OpenRouter key in Streamlit.""",
    },
    {
        "title": "[3.6] Set CORS_ORIGINS to Streamlit Cloud URL on API",
        "milestone": 4,
        "labels": ["phase-3", "priority-high", "type-deploy"],
        "body": """## Task
Allow requests from Streamlit Cloud origin only.""",
    },
    {
        "title": "[3.7] Production smoke test end-to-end",
        "milestone": 4,
        "labels": ["phase-3", "priority-high", "type-test"],
        "body": """## Task
On live URLs: lesson → chat → correction → save → past sessions.""",
    },
    {
        "title": "[3.8] Document deployment steps in README",
        "milestone": 4,
        "labels": ["phase-3", "priority-medium", "type-deploy"],
        "body": """## Task
Document deploy steps; note ephemeral SQLite on free tier.

## Files
- `README.md`""",
    },
    # Phase 4 — Testing
    {
        "title": "[4.1] Unit test: strip_json_from_response",
        "milestone": 5,
        "labels": ["phase-4", "priority-high", "type-test"],
        "body": """## Task
Verify JSON block removed and conversational text preserved.""",
    },
    {
        "title": "[4.2] Unit test: extract_feedback",
        "milestone": 5,
        "labels": ["phase-4", "priority-high", "type-test"],
        "body": """## Task
Valid JSON parsed; invalid returns empty list.""",
    },
    {
        "title": "[4.3] Unit test: openrouter error handling (mocked)",
        "milestone": 5,
        "labels": ["phase-4", "priority-high", "type-test"],
        "body": """## Task
Mock 429/timeout → correct exception types.""",
    },
    {
        "title": "[4.4] Unit test: conversation.send_message (mocked LLM)",
        "milestone": 5,
        "labels": ["phase-4", "priority-high", "type-test"],
        "body": """## Task
Full orchestration flow with mocked LLM response.""",
    },
    {
        "title": "[4.5] Integration test: session_repo.save",
        "milestone": 5,
        "labels": ["phase-4", "priority-high", "type-test"],
        "body": """## Task
Verify data written correctly to SQLite.""",
    },
    {
        "title": "[4.6] API test: GET /lessons",
        "milestone": 5,
        "labels": ["phase-4", "priority-high", "type-test"],
        "body": """## Task
Returns all 5 lessons.""",
    },
    {
        "title": "[4.7] API test: POST /chat/message",
        "milestone": 5,
        "labels": ["phase-4", "priority-high", "type-test"],
        "body": """## Task
Returns clean reply + corrections.""",
    },
    {
        "title": "[4.8] API test: POST /sessions",
        "milestone": 5,
        "labels": ["phase-4", "priority-high", "type-test"],
        "body": """## Task
Saves session and returns summary with score fields.""",
    },
    {
        "title": "[4.9] Manual E2E test: Streamlit → API → OpenRouter",
        "milestone": 5,
        "labels": ["phase-4", "priority-high", "type-test"],
        "body": """## Task
Full user journey with real API key.

## Reference
backend.md — §15 Testing Plan""",
    },
]


def main() -> int:
    created = []
    failed = []
    for issue in ISSUES:
        cmd = [
            "gh",
            "api",
            f"repos/{REPO}/issues",
            "-f",
            f"title={issue['title']}",
            "-f",
            f"body={issue['body']}",
            "-f",
            f"milestone={issue['milestone']}",
        ]
        for label in issue["labels"]:
            cmd.extend(["-f", f"labels[]={label}"])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            created.append((data["number"], issue["title"]))
            print(f"Created #{data['number']}: {issue['title']}")
        else:
            failed.append((issue["title"], result.stderr))
            print(f"FAILED: {issue['title']}\n{result.stderr}", file=sys.stderr)

    print(f"\nCreated {len(created)} issues, {len(failed)} failed.")
    if failed:
        for title, err in failed:
            print(f"  - {title}: {err}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
