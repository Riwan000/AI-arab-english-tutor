# Database Design
# AI English Tutor for Arabic Speakers — Phase 1 MVP

**Version:** 1.0  
**Status:** Implemented  
**Engine:** SQLite  
**File:** `database/english_tutor.db`  
**References:** [prd.md](prd.md) · [hld.md](hld.md) · [tech-stack.md](tech-stack.md)

---

# 1. Overview

SQLite stores completed learning sessions after a conversation ends. During an active session, all state lives in **Streamlit session state**. The database is the durable record for session summaries, message history, grammar corrections, and the past-sessions sidebar.

### Design decisions (confirmed)

| Decision | Choice |
|----------|--------|
| Required for MVP? | **Yes** — every completed session must be saved |
| Save triggers | **End Session** and **Start New Session** |
| Summary fields | Stored on `conversations` row |
| Corrections | Linked to user `messages` via `message_id` FK |
| Message metadata | `timestamp`, `lesson_id`, `sequence`, `has_correction` |
| Vocabulary | Persisted as JSON on `conversations` |
| Lesson reference | Both `lesson_id` and `lesson_title` |
| Timestamps | Real per-message UTC ISO timestamps |
| Retention | **5 days** — auto-purged on app startup |
| Read UI | Simple past session summary in sidebar |

---

# 2. Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       conversations                          │
│─────────────────────────────────────────────────────────────│
│ id (PK)                                                      │
│ lesson_id, lesson_title                                      │
│ created_at, ended_at                                         │
│ grammar_score, exchange_count, mistake_count                 │
│ vocabulary (JSON), recommendation, model_used                │
└───────────────┬─────────────────────────┬───────────────────┘
                │ 1:N                     │ 1:N
                ▼                         ▼
┌───────────────────────────┐   ┌─────────────────────────────┐
│         messages          │   │      grammar_feedback        │
│───────────────────────────│   │─────────────────────────────│
│ id (PK)                   │◄──│ message_id (FK)              │
│ conversation_id (FK)      │   │ conversation_id (FK)         │
│ role, content             │   │ mistake_type                 │
│ timestamp, sequence       │   │ wrong_text, corrected_text   │
│ lesson_id                 │   │ english_explanation          │
│ has_correction            │   │ arabic_explanation, tip      │
└───────────────────────────┘   └─────────────────────────────┘
```

**Cascade:** Deleting a `conversations` row deletes all related `messages` and `grammar_feedback` rows.

---

# 3. Schema

## 3.1 `conversations`

One row per completed learning session.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | PK | Auto-increment session ID |
| `lesson_id` | TEXT | NOT NULL | Lesson slug, e.g. `present_simple` |
| `lesson_title` | TEXT | NOT NULL | Display name, e.g. `Present Simple` |
| `created_at` | TEXT | NOT NULL | ISO 8601 UTC — first message timestamp |
| `ended_at` | TEXT | NOT NULL | ISO 8601 UTC — when session was saved |
| `grammar_score` | INTEGER | YES | 0–100 grammar percentage |
| `exchange_count` | INTEGER | YES | Number of user messages |
| `mistake_count` | INTEGER | YES | Total grammar corrections |
| `vocabulary` | TEXT | YES | JSON array, e.g. `["Breakfast","Office"]` |
| `recommendation` | TEXT | YES | Suggested next step for learner |
| `model_used` | TEXT | YES | OpenRouter model slug from env |

**Index:** `idx_conversations_ended_at` on `ended_at` (retention purge + ordering).

---

## 3.2 `messages`

Full conversation transcript with per-message metadata.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | PK | Auto-increment message ID |
| `conversation_id` | INTEGER | FK | Parent session |
| `role` | TEXT | NOT NULL | `user` or `assistant` |
| `content` | TEXT | NOT NULL | Message text |
| `timestamp` | TEXT | NOT NULL | ISO 8601 UTC — when message was sent |
| `sequence` | INTEGER | NOT NULL | 0-based order in conversation |
| `lesson_id` | TEXT | YES | Lesson active when message was sent |
| `has_correction` | INTEGER | NOT NULL | `1` if assistant message includes corrections |

**Index:** `idx_messages_conversation_id` on `conversation_id`.

---

## 3.3 `grammar_feedback`

Individual grammar corrections, linked to the **user message** that contained the mistake.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | PK | Auto-increment feedback ID |
| `conversation_id` | INTEGER | FK | Parent session |
| `message_id` | INTEGER | FK | The user message with the mistake |
| `mistake_type` | TEXT | YES | e.g. `Verb Form`, `Articles` |
| `wrong_text` | TEXT | YES | Incorrect fragment |
| `corrected_text` | TEXT | YES | Corrected form |
| `english_explanation` | TEXT | YES | Grammar rule in English |
| `arabic_explanation` | TEXT | YES | Explanation in Modern Standard Arabic |
| `tip` | TEXT | YES | Encouraging practice suggestion |

**Index:** `idx_grammar_feedback_conversation_id` on `conversation_id`.

---

## 3.4 `schema_version`

Internal migration tracking.

| Column | Type | Description |
|--------|------|-------------|
| `version` | INTEGER | Current schema version (`2`) |

---

# 4. SQL DDL

```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL,
    lesson_title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    grammar_score INTEGER,
    exchange_count INTEGER,
    mistake_count INTEGER,
    vocabulary TEXT,
    recommendation TEXT,
    model_used TEXT
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    lesson_id TEXT,
    has_correction INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE grammar_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    mistake_type TEXT,
    wrong_text TEXT,
    corrected_text TEXT,
    english_explanation TEXT,
    arabic_explanation TEXT,
    tip TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

CREATE INDEX idx_conversations_ended_at ON conversations(ended_at);
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_grammar_feedback_conversation_id ON grammar_feedback(conversation_id);
```

---

# 5. Write Path

## 5.1 When data is saved

| Trigger | Location | Behavior |
|---------|----------|----------|
| Summary screen loads | `components/summary.py` → `persist_session()` | Saves after score is calculated |
| **Start New Session** clicked | `components/summary.py` → `persist_session()` | Saves if not already persisted, then resets state |

**Duplicate guard:** `st.session_state.session_persisted` prevents double-writes when both triggers fire.

## 5.2 Save sequence

```
1. INSERT conversations          (summary fields + lesson metadata)
2. INSERT messages (in order)      (map sequence index → message id)
3. INSERT grammar_feedback         (link message_id via message_index)
```

## 5.3 Session state → database mapping

| Session state | Database target |
|---------------|-----------------|
| `lesson.id` | `conversations.lesson_id` |
| `lesson.title` | `conversations.lesson_title` |
| `messages[0].timestamp` | `conversations.created_at` |
| `score.grammar` | `conversations.grammar_score` |
| `score.exchanges` | `conversations.exchange_count` |
| `score.mistake_count` | `conversations.mistake_count` |
| `score.vocabulary` | `conversations.vocabulary` (JSON) |
| `score.recommendation` | `conversations.recommendation` |
| `DEFAULT_MODEL` env | `conversations.model_used` |
| `messages[]` | `messages` table (one row each) |
| `mistakes[]` + `message_index` | `grammar_feedback` table |

## 5.4 Message metadata at write time

Set in `components/chat.py` when each message is created:

```python
{
    "role": "user" | "assistant",
    "content": "...",
    "timestamp": "2026-08-07T01:30:00+00:00",  # UTC ISO
    "lesson_id": "present_simple",
    "has_correction": True | False,            # assistant only
    "feedback": [...]                            # assistant only (not stored on messages row)
}
```

Mistakes carry `message_index` pointing to the user message sequence index:

```python
{
    "mistake_type": "Verb Form",
    "wrong_text": "I eating",
    "correct_text": "I eat",
    "english_explanation": "...",
    "arabic_explanation": "...",
    "tip": "...",
    "message_index": 3
}
```

---

# 6. Read Path

## 6.1 Past sessions list

**Function:** `list_past_sessions(limit=20)`  
**Used by:** `components/sidebar.py` → `render_past_sessions()`  
**Returns:** Latest sessions ordered by `ended_at DESC`

```python
{
    "id": 1,
    "lesson_id": "present_simple",
    "lesson_title": "Present Simple",
    "ended_at": "2026-08-07T01:30:00+00:00",
    "grammar_score": 82,
    "exchange_count": 12,
    "mistake_count": 3,
    "recommendation": "Practice Present Simple again tomorrow."
}
```

## 6.2 Session detail

**Function:** `get_session_summary(conversation_id)`  
**Used by:** Sidebar expander for each past session  
**Returns:** Full conversation summary + aggregated mistake types

```python
{
    "id": 1,
    "lesson_id": "present_simple",
    "lesson_title": "Present Simple",
    "grammar_score": 82,
    "exchange_count": 12,
    "mistake_count": 3,
    "vocabulary": ["Breakfast", "Office", "Family"],
    "recommendation": "...",
    "mistake_types": [
        {"mistake_type": "Verb Form", "count": 2},
        {"mistake_type": "Articles", "count": 1}
    ]
}
```

---

# 7. Retention Policy

| Setting | Value |
|---------|-------|
| Retention period | **5 days** |
| Constant | `RETENTION_DAYS = 5` in `services/database.py` |
| Purge trigger | Once per Streamlit session on app startup (`app.py`) |
| Purge query | `DELETE FROM conversations WHERE ended_at < cutoff` |
| Cascade | Messages and grammar_feedback deleted via FK |

Sessions older than 5 days are permanently removed. No soft-delete or archive in Phase 1.

---

# 8. Migration

| Setting | Value |
|---------|-------|
| Current version | `SCHEMA_VERSION = 2` |
| Strategy | Drop and recreate tables if schema is outdated |
| Detection | Missing columns on `conversations` or version < 2 |

On schema mismatch, all existing data is dropped and tables are recreated. Acceptable for MVP; production would use incremental migrations.

---

# 9. Implementation Map

| File | Responsibility |
|------|----------------|
| `services/database.py` | Schema, save, read, purge, migration |
| `components/summary.py` | `persist_session()` — write on summary / new session |
| `components/chat.py` | Message timestamps, `lesson_id`, `message_index` on mistakes |
| `components/sidebar.py` | Past sessions UI |
| `app.py` | Retention purge on startup; `session_persisted` flag init |
| `models/feedback.py` | `GrammarFeedback` Pydantic model (source shape for corrections) |
| `models/conversation.py` | `Message`, `Conversation` Pydantic models |

---

# 10. Configuration

| Item | Location | Notes |
|------|----------|-------|
| DB file path | `database/english_tutor.db` | Auto-created on first save |
| Git ignore | `.gitignore` → `database/*.db` | DB file not committed |
| Foreign keys | `PRAGMA foreign_keys = ON` | Enabled per connection |
| Model tracking | `DEFAULT_MODEL` env var | Stored on each conversation |

---

# 11. Example Queries

### Latest 10 sessions

```sql
SELECT lesson_title, grammar_score, ended_at
FROM conversations
ORDER BY ended_at DESC
LIMIT 10;
```

### Mistake breakdown for a session

```sql
SELECT mistake_type, COUNT(*) AS count
FROM grammar_feedback
WHERE conversation_id = ?
GROUP BY mistake_type
ORDER BY count DESC;
```

### Full transcript for a session

```sql
SELECT role, content, timestamp, has_correction
FROM messages
WHERE conversation_id = ?
ORDER BY sequence;
```

### Corrections linked to user messages

```sql
SELECT m.content AS user_message, g.mistake_type, g.wrong_text, g.corrected_text
FROM grammar_feedback g
JOIN messages m ON g.message_id = m.id
WHERE g.conversation_id = ?
ORDER BY m.sequence;
```

---

# 12. Out of Scope (Phase 1)

- User accounts / authentication
- Multi-device sync
- Soft delete / undo
- Full message replay UI in sidebar (only summary shown)
- Analytics aggregation across lessons
- PostgreSQL migration
- Backup / export

---

# 13. Future Considerations (Phase 2+)

| Enhancement | Notes |
|-------------|-------|
| PostgreSQL | Replace SQLite for multi-user deployment |
| User table | `users` → `conversations.user_id` |
| Lesson analytics | Aggregate `grammar_score` by `lesson_id` |
| Message replay | Load full transcript from `messages` in a detail view |
| Configurable retention | Admin setting instead of hardcoded 5 days |
| Soft delete | `deleted_at` column for GDPR compliance |

---

*Implemented in `services/database.py` (schema v2). Aligned with confirmed design decisions from Phase 1 planning.*
