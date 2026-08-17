# Project Brain — AI English Tutor for Arabic Speakers

**Note (2026-08-17):** Streamlit has been fully removed; the frontend is now the React app at `frontend/`. This document's architecture diagrams and directory map below still describe the old Streamlit-based split and are stale pending a full rewrite.

**Purpose of this document:** a single, code-verified reference to how this repository actually works today — architecture, request flows, every module's responsibility, the data model, prompt design, deployment, and known gaps. Unlike the planning docs in the repo root (`prd.md`, `hld.md`, `tech-stack.md`, `backend.md`, `db.md`, `directory.md`), which were written *before* implementation and are now partly historical, this document was produced by reading the current source tree directly (verified 2026-08-11, commit `99c187f`).

---

## 1. What this project is

A web app that teaches English grammar to Arabic-speaking beginners (A1–A2) through **lesson-constrained AI conversation**. The learner picks one grammar topic (e.g. Present Simple), reads a short explanation, then chats in English with an AI tutor that:

- stays within that lesson's grammar/vocabulary,
- corrects mistakes inline with a bilingual (English + Arabic) explanation,
- keeps the conversation going naturally instead of "stopping to review grammar,"
- and produces an end-of-session score + recommendation.

Core hypothesis being validated: lesson-aware AI conversation with bilingual feedback beats a generic chatbot for this audience.

---

## 2. Actual architecture (as implemented, not as planned)

The repo root docs describe a *migration plan* from a Streamlit monolith to a split frontend/backend. **That migration is complete.** The codebase today is a two-process, two-deployment-target system:

```
┌────────────────────────────┐        HTTPS / JSON        ┌─────────────────────────────────────┐
│   Streamlit frontend        │  ─────────────────────────►│   FastAPI backend (api/)             │
│   (app.py + components/)    │◄───────────────────────────│   services/ + repositories/ +        │
│   UI only — zero business   │        api_client.py       │   models/ + prompts/ + lessons/      │
│   logic, zero LLM/DB access │                             │                                       │
└────────────────────────────┘                             └───────────────┬───────────────────────┘
     Streamlit Cloud (deploy)                                              │
                                                                            ▼
                                                            ┌──────────────────────────┐
                                                            │  OpenRouter API            │
                                                            │  (LLM: default             │
                                                            │  openai/gpt-4.1)           │
                                                            └──────────────────────────┘
                                                                            │
                                                                            ▼
                                                            ┌──────────────────────────┐
                                                            │  SQLite                    │
                                                            │  database/english_tutor.db │
                                                            │  (Render disk, optional)   │
                                                            └──────────────────────────┘
```

**Key architectural fact:** the Streamlit layer contains **no** direct imports of `services/`, `repositories/`, or `openrouter` — this was enforced by `scripts/verify_no_service_imports.py` during the migration (commit `67abc01`) and remains true. Every component talks to the backend exclusively through `api_client.py` over HTTP. `OPENROUTER_API_KEY` lives only in the backend's environment; it is never present in Streamlit secrets.

### Why split like this
- Hides the OpenRouter API key from the publicly-hosted Streamlit Cloud app.
- Lets the two halves deploy and scale independently (Streamlit Cloud + Render).
- Makes the backend swappable later for a non-Streamlit frontend without touching business logic.

### What is deliberately *not* here
No auth, no user accounts, no payments, no voice/speech, no WebSockets/streaming, no Redis, no Postgres, no per-user rate limiting. The chat API is **stateless** — the client resends the full message history on every request; there is no server-side "active session" concept. Only *completed* sessions are persisted.

---

## 3. Directory map (verified against the file tree)

```
AI-arab-english-tutor/
├── app.py                     Streamlit entry point — screen router only
├── api_client.py              HTTP client the Streamlit side uses to reach the API
│
├── api/                       FastAPI application
│   ├── main.py                App factory, CORS, lifespan (startup purge), error handler
│   ├── config.py               Settings (pydantic-settings, env-driven)
│   ├── dependencies.py         DI: get_session_repository()
│   ├── routes/
│   │   ├── health.py           GET /api/v1/health
│   │   ├── lessons.py          GET /api/v1/lessons, /lessons/{id}
│   │   ├── chat.py             POST /api/v1/chat/start, /chat/message
│   │   └── sessions.py         POST /api/v1/sessions, GET /sessions, /sessions/{id}
│   └── schemas/                Request models + thin response wrappers (thin — real
│                                shapes live in models/, schemas mostly re-export them)
│
├── services/                   Business logic — no HTTP, no UI, no direct SQL outside database.py
│   ├── conversation.py         Orchestrates a chat turn / session end (the core service)
│   ├── openrouter.py           LLM HTTP client + typed error translation
│   ├── grammar.py               Parses/strips the ```json correction block from LLM text
│   ├── lessons.py               Loads & in-memory-caches lessons/*.json
│   ├── scoring.py               Grammar score, vocabulary extraction, recommendation text
│   ├── database.py              Low-level SQLite: schema, migration, CRUD, purge
│   └── errors.py                AppError hierarchy → HTTP status/detail mapping
│
├── repositories/
│   └── session_repo.py          Thin façade over services/database.py (the only thing
│                                 api/routes and services/conversation touch for persistence)
│
├── models/                      Pydantic domain models shared by API schemas, services, UI
│   ├── lesson.py                 Lesson, LessonSummary
│   ├── conversation.py           Message, ChatResponse, SessionSummary, SessionListItem,
│   │                              SessionDetail, MistakeTypeCount, Conversation
│   └── feedback.py               GrammarFeedback
│
├── prompts/                     Prompt templates as YAML (editable without touching Python)
│   ├── system_prompt.yaml        Base tutor behavior + JSON correction-block format
│   ├── lesson_context.yaml       Per-lesson template (rules, vocab, level, language)
│   ├── start_conversation.yaml   Opening-message template
│   ├── prompt_loader.py          Cached YAML reader
│   └── prompt_builder.py         Fills templates + assembles the OpenRouter messages array
│
├── components/                  Streamlit UI — thin, calls api_client only
│   ├── sidebar.py                Lesson picker, live score/mistakes/vocab, End Session,
│   │                              past-sessions list (via API)
│   ├── lesson_view.py            Pre-chat lesson explanation screen
│   ├── chat.py                   Chat loop: renders history, starts + sends messages
│   ├── correction_card.py        Renders one bilingual correction card
│   └── summary.py                End-of-session screen; persists + displays summary
│
├── lessons/                     Static lesson content (5 JSON files, see §7)
├── database/                    SQLite file lives here at runtime (gitignored .db)
├── assets/                      Empty placeholder (icons/CSS not used yet)
│
├── scripts/
│   ├── start_api.sh              Render/Docker container entrypoint (uvicorn)
│   ├── verify_phase1.py          Checks Phase-1 service refactor completeness
│   ├── verify_phase2.py          Checks Phase-2 FastAPI layer completeness
│   ├── verify_phase2_exit.py     Phase-2 exit criteria / API smoke tests
│   ├── verify_api_client.py      Checks api_client.py covers all endpoints correctly
│   ├── verify_no_service_imports.py  Fails if any component imports services/* directly
│   └── create_backend_issues.py  One-off script that filed the GitHub issues for the
│                                  backend migration (historical, not part of runtime)
│
├── Dockerfile                    Backend-only image (uses requirements-api.txt)
├── render.yaml                   Render Blueprint for the API service
├── requirements.txt              Full stack (Streamlit + API) — for local two-process dev
├── requirements-api.txt          API-only deps — for the Docker/Render image
│
├── .env / .env.example           Backend secrets (OPENROUTER_API_KEY, DB path, CORS, ...)
├── .streamlit/secrets.toml(.example)  Frontend-only secret: BACKEND_URL
│
└── prd.md, hld.md, tech-stack.md, backend.md, db.md, directory.md
    Planning/design docs — see §12 for how they relate to this document.
```

---

## 4. Request flow — sending a chat message (end to end)

This is the central flow of the app; tracing it end to end explains most of the codebase.

```
1. Learner types in the Streamlit chat_input        (components/chat.py:_handle_user_message)
2. UI appends {role:"user", content, timestamp, lesson_id} to st.session_state.messages
3. api_client.send_message(lesson_id, history, user_text)
     → POST /api/v1/chat/message  {lesson_id, messages: [...history, {role:"user",...}]}
4. api/routes/chat.py: send_chat_message()
     → ChatMessageRequest validates: min 1 message, LAST message must have role "user"
     → body.split_history_and_user_text()  → (history, user_text)
5. services/conversation.send_message(lesson_id, history, user_text)
     a. lessons.get_lesson(lesson_id)               raises LessonNotFoundError (404) if missing
     b. history + [user message] → prompts.prompt_builder.build_messages(lesson, history)
        - system message = system_prompt.yaml + lesson_context.yaml (rules, vocab, level="A1–A2",
          native_language="Arabic") filled in via prompt_loader.py
        - then the full conversation history appended verbatim (role/content only)
     c. services.openrouter.chat_completion(messages)
        - POST {OPENROUTER_BASE_URL}/chat/completions, model=DEFAULT_MODEL, 30s timeout
        - raises LLMTimeoutError / LLMRateLimitError(429) / LLMError on failure
     d. services.grammar.extract_feedback(raw)   → parses the trailing ```json {...}``` block
        into list[GrammarFeedback] (silently returns [] on missing/malformed JSON)
     e. services.grammar.strip_json_from_response(raw) → same regex removes that block from
        the text the learner actually sees
     f. returns ChatResponse(reply=clean_text, corrections=[...])
6. FastAPI serializes ChatResponse as the HTTP response body
7. api_client.send_message returns the dict to chat.py
8. UI appends corrections' message_index = the just-added user message's index, pushes them
   into st.session_state.mistakes, appends the assistant message (with .feedback = corrections)
9. st.rerun() → components/correction_card.py renders each correction: ❌ wrong / ✅ correct /
   English rule / Arabic rule (بالعربية) / 💡 tip
```

**Failure behavior:** any HTTP/timeout error inside `api_client._request_post` shows an `st.error()` banner and returns a safe fallback (`{"reply": "", "corrections": []}`); `chat.py` then pops the just-appended user message back off so the UI doesn't show an orphaned unanswered turn.

### Starting a conversation
`POST /api/v1/chat/start` is nearly identical but calls `conversation.start_conversation(lesson_id)`, which builds messages with `start=True` — this appends a single synthetic user turn from `start_conversation.yaml` ("Start a guided conversation to practice {title}...") instead of real history, so the LLM produces the opening greeting/question.

### Ending a session
```
components/summary.py: render_summary() → persist_session() (idempotent, guarded by
  st.session_state.session_persisted so End Session + Start New Session can't double-save)
  → api_client.save_session(lesson_id, messages, mistakes)
  → POST /api/v1/sessions
  → api/routes/sessions.py: create_session()
  → services.conversation.end_session(lesson_id, messages, mistakes)
      - returns None (→ EmptySessionError, HTTP 400) if messages is empty
      - services.scoring.calculate_session_summary(messages, mistakes, lesson.title):
          grammar_score = max(0, 100 - mistake_count*10)
          exchanges     = count of role=="user" messages
          mistake_types = de-duplicated mistake_type list, order preserved
          vocabulary    = top 8 non-stopword words (>2 chars) from user messages, capitalized
          recommendation = "Practice {lesson} again tomorrow." if score<70
                            "Excellent work! Try a harder lesson next." if score>=90
                            else None
      - repositories.SessionRepository().save(...) → services.database.save_session(...)
        writes 1 conversations row, N messages rows, M grammar_feedback rows (see §8)
  → returns SessionSummary → UI shows score/exchanges/mistakes/vocabulary/recommendation
```

---

## 5. Layer-by-layer responsibilities

| Layer | Files | Owns | Must never do |
|---|---|---|---|
| **Presentation** | `app.py`, `components/*` | Rendering, `st.session_state` wiring, screen routing (lesson → chat → summary) | Call `services/*`, `openrouter`, or SQLite directly |
| **HTTP client** | `api_client.py` | All outbound calls to the backend; uniform timeout/error handling; strips UI-only fields before sending | Contain business logic (scoring, prompt building) |
| **API** | `api/main.py`, `api/routes/*`, `api/schemas/*` | Request validation, routing, CORS, mapping `AppError` → JSON error response | Business logic — routes are thin, they call straight into `services/conversation.py` |
| **Services** | `services/*` | Orchestration (`conversation.py`), LLM I/O, prompt-response parsing, scoring, lesson loading, exception typing | HTTP request/response objects, Streamlit imports |
| **Repositories** | `repositories/session_repo.py` | The one sanctioned entry point into persistence for the rest of the app | Raw SQL (delegates to `services/database.py`) |
| **Data access** | `services/database.py` | Schema DDL, migration-by-drop, SQLite connection, CRUD, retention purge | Business rules (scoring, validation) |
| **Models** | `models/*` | Canonical Pydantic shapes reused by API schemas, services, and (as dicts) the UI | — |
| **Prompts** | `prompts/*.yaml` + loader/builder | All LLM-facing text; editable by non-engineers | Prompt text hardcoded in `.py` files |
| **Static content** | `lessons/*.json` | Grammar content per lesson | — |

---

## 6. Configuration surface

### Backend (`api/config.py`, `pydantic-settings`, reads `.env`)

| Variable | Default | Used by |
|---|---|---|
| `OPENROUTER_API_KEY` | `""` (required in practice) | `services/openrouter.py` — raises `LLMError` if unset when a call is attempted |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | `services/openrouter.py` |
| `DEFAULT_MODEL` | `openai/gpt-4.1` | `services/openrouter.py`; also echoed in `/api/v1/health` and stored on each saved conversation |
| `DATABASE_PATH` | `database/english_tutor.db` | `services/database.py` |
| `RETENTION_DAYS` | `5` | Startup purge (see §9) |
| `CORS_ORIGINS` | `["http://localhost:8501"]` | `api/main.py` CORSMiddleware; comma-separated string parsed via a `field_validator` |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | Only relevant for the raw `uvicorn` command; Render overrides port via `$PORT` (see `scripts/start_api.sh`) |

`Settings.apply_to_environ()` is called once in the FastAPI `lifespan` — it pushes the pydantic-settings values back into `os.environ` so the older module-level globals in `services/openrouter.py` and `services/database.py` (which read `os.getenv(...)` at import time) get overridden with the real runtime config. This is a deliberate bridge between the new `api/config.py` settings object and legacy module globals — worth knowing if you ever see stale config: check whether `apply_to_environ()` ran before the module was imported.

### Frontend (`.streamlit/secrets.toml`)

Only one key: `BACKEND_URL` (default `http://localhost:8000` if unset). `OPENROUTER_API_KEY` must **never** appear here — see the warning comments in `.streamlit/secrets.toml.example` and `README.md`.

---

## 7. Lesson content model

Static JSON files in `lessons/` (currently 5: `present_simple`, `present_continuous`, `past_simple`, `articles`, `prepositions` — **not** `daily_conversation`, which the PRD lists but was never added).

```json
{
  "id": "present_simple",
  "title": "Present Simple",
  "description": "...",
  "examples": ["I eat breakfast every morning.", "..."],
  "grammar_rules": ["Use base verb form for I/you/we/they", "..."],
  "allowed_vocabulary": ["eat", "work", "live", "..."],
  "negative_form": ["I don't drink coffee.", "..."],
  "question_form": ["Do you work?", "..."],
  "tips": ["Remember: he/she/it needs -s on the verb.", "..."]
}
```

`services/lessons.py` loads every `*.json` under `lessons/` into a module-level dict on first access (`_lessons_cache`), keyed by `id`, validated through the `Lesson` Pydantic model. This cache lives for the process lifetime — adding a new lesson JSON file requires a backend restart to be picked up.

---

## 8. Database schema (SQLite, `database/english_tutor.db`)

Only **completed** sessions are stored — the active chat lives purely in `st.session_state` until `End Session` / `Start New Session` triggers a save.

```
conversations (1) ──< (N) messages ──< (N) grammar_feedback
                 └──────────────────< (N) grammar_feedback   (also FK'd via conversation_id)
```

```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL,
    lesson_title TEXT NOT NULL,
    created_at TEXT NOT NULL,          -- first message's timestamp
    ended_at TEXT NOT NULL,            -- save time (UTC ISO)
    grammar_score INTEGER,
    exchange_count INTEGER,
    mistake_count INTEGER,
    vocabulary TEXT,                   -- JSON array string
    recommendation TEXT,
    model_used TEXT
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,                -- "user" | "assistant"
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    sequence INTEGER NOT NULL,         -- 0-based order
    lesson_id TEXT,
    has_correction INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE grammar_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    mistake_type TEXT,
    wrong_text TEXT,
    corrected_text TEXT,
    english_explanation TEXT,
    arabic_explanation TEXT,
    tip TEXT
);

CREATE INDEX idx_conversations_ended_at ON conversations(ended_at);
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_grammar_feedback_conversation_id ON grammar_feedback(conversation_id);
```

`grammar_feedback.message_id` is resolved from the `message_index` carried on each `GrammarFeedback` object at persist time — a correction is only saved if its `message_index` maps to a real message written in the same transaction; otherwise it's silently dropped (`services/database.py:save_session`).

### Schema migration strategy
`services/database.py._needs_migration()` checks table existence, a fixed set of required columns, and a `schema_version` table (current version `2`). If anything is missing/stale, **all three tables are dropped and recreated** — there is no incremental migration. This is acceptable for MVP but means a schema bump destroys all historical sessions; there's no backup/export path today.

### Retention
`purge_old_conversations()` deletes `conversations` (and cascades to `messages`/`grammar_feedback`) where `ended_at < now - RETENTION_DAYS`. This runs once at FastAPI startup (`api/main.py` lifespan), wrapped in `try/except OSError: pass` so a missing/unwritable DB directory doesn't fail the health check.

### Persistence on Render
SQLite is file-based and **ephemeral by default** on Render — data resets on every redeploy unless a persistent disk is attached. `render.yaml` deploys on the **free** plan (no disk support). Issue #66 (see commits `1a4e484`, `99c187f`) documents attaching a 1 GB disk at `/app/database` on the **Starter** plan (~$7/mo) as an optional upgrade path — this must be done manually in the Render dashboard, not via `render.yaml`, because disks aren't supported on free-tier blueprints.

---

## 9. AI / prompting design

**Single-call pattern:** one OpenRouter chat-completion request per turn returns both the conversational reply *and* (when applicable) a trailing JSON block of structured corrections — no separate translation or grammar-checking service.

### Prompt assembly (`prompts/prompt_builder.py`)
```
messages = [
  { role: "system", content: system_prompt.yaml + lesson_context.yaml filled in },
  ...history (role/content only, no metadata forwarded to the LLM),
  (if start=True) { role: "user", content: start_conversation.yaml filled in }
]
```

- `system_prompt.yaml` — tutor persona, hard rules ("never say Wrong", bilingual explanation requirement, A1–A2 English), and the exact JSON schema the model must emit for corrections.
- `lesson_context.yaml` — templated with `{title}`, `{description}`, `{grammar_rules}` (joined as a bullet list), `{vocabulary}` (comma-joined), `{student_level}` (hardcoded `"A1–A2 beginner"`), `{native_language}` (hardcoded `"Arabic"`).
- `start_conversation.yaml` — the one-line synthetic opening prompt.

All three are YAML so prompt wording can change without touching Python; `prompt_loader.py` caches parsed YAML per-process via `lru_cache`.

### Correction JSON contract
The system prompt instructs the model to end its reply with:
```json
{
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
`services/grammar.py` uses one regex (`r"```json\s*\{.*?\}\s*```"`, `DOTALL`) both to extract this block (`extract_feedback`) and to strip it from the visible reply (`strip_json_from_response`). Malformed JSON or a schema mismatch on any single correction item is swallowed (`except (TypeError, ValueError): continue` / `except json.JSONDecodeError: return []`) — the learner still gets the conversational text, just without structured corrections. This is a deliberate graceful-degradation choice, not a bug.

### Model selection
OpenRouter abstracts the actual provider — swapping `DEFAULT_MODEL` (e.g. `openai/gpt-4.1` → a Claude or Gemini slug) requires no code change, just an env var change.

---

## 10. Error handling

| Origin | Exception | HTTP status | User-facing message |
|---|---|---|---|
| `openrouter.py` | `LLMTimeoutError` | 502 | "The AI tutor took too long to respond. Please try again." |
| `openrouter.py` | `LLMRateLimitError` (upstream 429) | 502 | "Too many requests. Please wait a moment and try again." |
| `openrouter.py` | `LLMError` (other HTTP/network failure, or missing API key) | 502 | "The AI tutor is temporarily unavailable. Please try again." |
| `lessons.py` | `LessonNotFoundError` | 404 | "Lesson not found" |
| `sessions.py` route | `EmptySessionError` | 400 | "No messages to save" |
| `sessions.py` route | `SessionNotFoundError` | 404 | "Session not found" |
| FastAPI (pydantic) | validation error | 422 | field-level detail (e.g. last message not from `user`) |
| `api_client.py` | any `httpx` timeout/HTTP/network error | — | `st.error()` banner with a fixed fallback message; caller gets a safe empty-shaped fallback (`{"reply": "", "corrections": []}` or `None`) |

All custom exceptions derive from `services.errors.AppError(status_code, detail)`; a single `@app.exception_handler(AppError)` in `api/main.py` converts any of them to `{"detail": ...}` JSON. This is the entire error-handling strategy — no logging framework, no Sentry/observability wiring currently exists.

---

## 11. Deployment

Two independent deploys, no shared runtime:

| Component | Host | Notes |
|---|---|---|
| Frontend (`app.py`) | Streamlit Community Cloud | Free; reads `BACKEND_URL` from its Secrets UI |
| Backend (`api/`) | Render (Docker, `render.yaml` Blueprint) | Free plan by default; health check `GET /api/v1/health`; spins down after ~15 min idle (cold start 30–60s on next request) |
| Database | SQLite file on the Render instance | Ephemeral on free tier; persistent only with a Starter-plan disk mounted at `/app/database` (manual dashboard step, not in `render.yaml`) |
| LLM | OpenRouter | Pay-per-use, key held only in Render env vars |

`Dockerfile` builds from `requirements-api.txt` only (no Streamlit in the API image) and runs `scripts/start_api.sh`, which `mkdir -p`'s the SQLite directory (derived from `$DATABASE_PATH`) before `exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"` — using Render's injected `$PORT` rather than the fixed `8000` from `.env`, which is why the most recent commit (`99c187f`) fixed a health-check failure that appeared after the disk config change (the container was still binding the stale hardcoded port in some path).

Local two-process dev:
```bash
# Terminal 1
uvicorn api.main:app --reload --port 8000

# Terminal 2
BACKEND_URL=http://localhost:8000 streamlit run app.py
```

---

## 12. How this document relates to the other docs in the repo root

The root-level docs (`prd.md`, `hld.md`, `tech-stack.md`, `backend.md`, `db.md`, `directory.md`) were written **in sequence as design documents before/during the Phase 1→2 migration** (see the git log in §13). They're still useful as *rationale* — why a decision was made — but several of them describe target states that are now simply "the current state," and a few describe gaps that have since been closed. Treat this file (`docs/PROJECT_BRAIN.md`) as the source of truth for **what the code does today**; treat the root docs as the **design history and reasoning** behind it.

Specifically, `hld.md` §15 ("Known Gaps") is now partly stale:

| Gap listed in `hld.md` | Current reality |
|---|---|
| SQLite persistence "not yet wired" | **Resolved.** Fully wired via `services/conversation.end_session` → `SessionRepository.save`. |
| API error handling "TODO" | **Resolved.** See §10 above. |
| "Daily Conversation" lesson missing | **Still missing** — only 5 of the 6 PRD-listed lessons exist. |
| Previous mistakes injected into prompt | **Still not implemented** — `prompt_builder.build_messages` takes lesson + raw history only; the `mistakes` list is never fed back into the system/lesson-context prompt. Each turn's grammar detection is independent of earlier mistakes in the same session. |
| Live vocabulary tracking in sidebar during chat | **Still not implemented** — `st.session_state.vocabulary` is only populated once, from the `/api/v1/sessions` save response, after `End Session`. During an active conversation the sidebar's "Vocabulary" section stays empty. |
| Fluency metric | **Still not implemented.** |
| Right panel UI (PRD's 3-column layout) | **Still folded into the sidebar**, as originally accepted for MVP. |

---

## 13. Evolution (from `git log`)

```
81ab1d9  Initial scaffold for AI English Tutor Phase 1 MVP.
3e05ba0  Add Phase 0 foundation and session persistence layer.
256c699  Implement Phase 1 service refactor and YAML prompt templates.
5c7db5c  Add FastAPI API layer for Phase 2 endpoints (issues #30-#46).
866f4aa  Implement api_client HTTP methods for all API endpoints (issue #47).
3916611  Migrate Streamlit to api_client and add error handling (issues #48-#53).
67abc01  Remove Streamlit service imports and OpenRouter config (issues #54-#55).
ca14b4e  Add Dockerfile for API deployment (issue #56).
5d68439  Add API-only requirements split and document two-process dev setup (issues #57, #58).
78a574b  Add Phase 2 exit verification and API smoke tests (issues #59-#63).
afd643e  Add Render Blueprint and deployment docs for API hosting.
1a4e484  Configure persistent SQLite disk on Render for issue #66.
99c187f  Fix Render deploy health check failure after disk config change.
```

This is a textbook strangler-fig migration: the app started as a Streamlit monolith with direct `services/` calls, then business logic was extracted behind a stable interface (`services/conversation.py`), a FastAPI layer was added *alongside* the monolith, the Streamlit side was cut over to `api_client.py`, direct service imports were deleted and mechanically verified gone (`verify_no_service_imports.py`), and finally the two halves were deployed to separate hosts.

---

## 14. Verification scripts (developer tooling, not runtime code)

These live in `scripts/` and were used as gates during the migration; they're safe to re-run as regression checks but are not imported by the app itself:

- `verify_phase1.py` — confirms the Phase 1 service refactor (errors.py, lessons.py, JSON stripping, conversation.py, session_repo.py) exists and is wired.
- `verify_phase2.py` / `verify_phase2_exit.py` — confirms the FastAPI layer + exit criteria for Phase 2 (routes exist, respond correctly, CORS configured).
- `verify_api_client.py` — confirms `api_client.py` implements every endpoint the backend exposes, with correct error handling.
- `verify_no_service_imports.py` — greps `components/` (and `app.py`) for forbidden imports of `services`, `repositories`, or `openrouter`; fails the build if found. This is the mechanical guarantee behind the "presentation never touches business logic" rule in §5.
- `create_backend_issues.py` — one-off script (1154 lines) that filed the GitHub issues referenced in the commit messages above (#30–#66). Historical artifact of the planning process, not part of the app.

---

## 15. Quick reference — where do I change X?

| I want to... | Touch this |
|---|---|
| Change tutor personality / correction JSON format | `prompts/system_prompt.yaml` |
| Add a new grammar lesson | New `lessons/<id>.json` file matching the `Lesson` schema (§7) — requires backend restart (in-memory cache) |
| Change how grammar score / recommendation is calculated | `services/scoring.py` |
| Add a new API endpoint | `api/routes/*.py` + matching `api/schemas/*.py` + service function in `services/` |
| Change what gets persisted per session | `services/database.py` (schema + `save_session`) — remember to bump `SCHEMA_VERSION` (this **drops all existing data**, see §8) |
| Change the LLM model/provider | `DEFAULT_MODEL` env var — no code change needed |
| Change Streamlit screens/flow | `app.py` (routing) + relevant file in `components/` |
| Change how the frontend talks to the backend | `api_client.py` only — never call `services/*` from `components/` (enforced by `verify_no_service_imports.py`) |
| Change CORS / deployment env vars | `api/config.py` (schema) + `.env` / Render dashboard / `render.yaml` |
