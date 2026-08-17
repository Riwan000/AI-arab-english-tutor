"""Postgres persistence for accounts, usage and completed conversations.

Schema is owned by the versioned migrations in `supabase/migrations/` — this
module only reads and writes data, it never creates or alters tables.
"""

import os
from datetime import date, datetime, timedelta, timezone

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "5"))

_pool: ConnectionPool | None = None


def open_pool() -> ConnectionPool:
    """Open (or return) the module-level connection pool.

    `DATABASE_URL` is read here rather than at import time so callers can sync
    settings into `os.environ` first — importing this module must never require
    a configured database.
    """
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=os.environ["DATABASE_URL"],
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def close_pool() -> None:
    """Close the connection pool, if one is open."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_pool() -> ConnectionPool:
    """Return the pool, opening it on first use."""
    return open_pool()


def get_connection():
    """Context manager yielding a pooled connection (returned, not closed)."""
    return get_pool().connection()


def _isoformat_temporals(row: dict) -> dict:
    """Render date/timestamp columns back as ISO strings.

    Postgres returns real `date`/`datetime` objects where the previous storage
    engine returned the ISO text the app wrote. Callers (and the Pydantic
    response models, e.g. `SessionListItem.ended_at: str`) still expect strings,
    so normalise on the way out and keep the row shape unchanged.
    """
    return {
        key: value.isoformat() if isinstance(value, (datetime, date)) else value
        for key, value in row.items()
    }


AUTH_ATTEMPTS_RETENTION_DAYS = 2


def purge_old_auth_attempts(retention_days: int = AUTH_ATTEMPTS_RETENTION_DAYS) -> int:
    """Delete auth_attempts rows older than retention_days. Returns rows deleted.

    The counter is only ever read for today's window_date, so a couple of days
    of retention is plenty — this just keeps the table from growing unbounded
    (each distinct (ip, email, day) is its own row).
    """
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=retention_days)).isoformat()
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM auth_attempts WHERE window_date < %s", (cutoff,))
        return cursor.rowcount


def purge_old_conversations(retention_days: int = RETENTION_DAYS) -> int:
    """Delete conversations older than retention_days. Returns rows deleted."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM conversations WHERE ended_at < %s",
            (cutoff,),
        )
        return cursor.rowcount


def save_session(
    lesson: dict,
    messages: list[dict],
    mistakes: list,
    summary: dict,
    model_used: str | None = None,
    user_id: int | None = None,
    mode: str = "lesson",
) -> int | None:
    """Persist a completed session. Returns conversation id or None if nothing to save."""
    if not messages:
        return None

    now = datetime.now(timezone.utc).isoformat()
    created_at = messages[0].get("timestamp", now)
    model = model_used or os.getenv("DEFAULT_MODEL", "")

    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO conversations (
                user_id, lesson_id, lesson_title, mode, created_at, ended_at,
                grammar_score, exchange_count, mistake_count,
                vocabulary, recommendation, model_used
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                lesson["id"],
                lesson["title"],
                mode,
                created_at,
                now,
                summary.get("grammar"),
                summary.get("exchanges"),
                summary.get("mistake_count"),
                Jsonb(summary.get("vocabulary", [])),
                summary.get("recommendation"),
                model,
            ),
        ).fetchone()
        conversation_id = row["id"]
        message_ids_by_index: dict[int, int] = {}

        for sequence, msg in enumerate(messages):
            message_row = conn.execute(
                """
                INSERT INTO messages (
                    conversation_id, role, content, timestamp,
                    sequence, lesson_id, has_correction
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    conversation_id,
                    msg["role"],
                    msg["content"],
                    msg.get("timestamp", now),
                    sequence,
                    msg.get("lesson_id", lesson["id"]),
                    bool(msg.get("has_correction") or msg.get("feedback")),
                ),
            ).fetchone()
            message_ids_by_index[sequence] = message_row["id"]

        for mistake in mistakes:
            data = mistake.model_dump() if hasattr(mistake, "model_dump") else dict(mistake)
            message_index = data.pop("message_index", None)
            if message_index is None:
                continue

            message_id = message_ids_by_index.get(message_index)
            if message_id is None:
                continue

            conn.execute(
                """
                INSERT INTO grammar_feedback (
                    conversation_id, message_id, mistake_type,
                    wrong_text, corrected_text, english_explanation,
                    arabic_explanation, tip
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    conversation_id,
                    message_id,
                    data.get("mistake_type"),
                    data.get("wrong_text"),
                    data.get("correct_text") or data.get("corrected_text"),
                    data.get("english_explanation"),
                    data.get("arabic_explanation"),
                    data.get("tip", ""),
                ),
            )

        return conversation_id


def list_past_sessions(limit: int = 30, *, user_id: int) -> list[dict]:
    """List the caller's own sessions, newest first.

    `user_id` is keyword-only and required so ownership filtering can never be
    skipped — or accidentally satisfied by a positional `limit`. Rows with a
    NULL `user_id` (saved before ownership existed) belong to nobody and are
    never returned.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, lesson_id, lesson_title, ended_at,
                   grammar_score, exchange_count, mistake_count, recommendation
            FROM conversations
            WHERE user_id = %s
            ORDER BY ended_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
    return [_isoformat_temporals(row) for row in rows]


def get_user_learning_profile(user_id: int, session_limit: int = 5) -> dict:
    """Fetch user's recent sessions and top recurring grammar mistakes across all their sessions."""
    with get_connection() as conn:
        sessions = conn.execute(
            """
            SELECT lesson_title, grammar_score, recommendation, ended_at
            FROM conversations
            WHERE user_id = %s
            ORDER BY ended_at DESC
            LIMIT %s
            """,
            (user_id, session_limit),
        ).fetchall()

        mistakes = conn.execute(
            """
            SELECT gf.mistake_type, COUNT(*) as count
            FROM grammar_feedback gf
            JOIN conversations c ON gf.conversation_id = c.id
            WHERE c.user_id = %s AND gf.mistake_type IS NOT NULL AND gf.mistake_type != ''
            GROUP BY gf.mistake_type
            ORDER BY count DESC
            LIMIT 5
            """,
            (user_id,),
        ).fetchall()

    return {
        "recent_sessions": [_isoformat_temporals(row) for row in sessions],
        "top_mistakes": [row["mistake_type"] for row in mistakes],
    }



def get_session_summary(conversation_id: int, *, user_id: int) -> dict | None:
    """Fetch one session owned by `user_id`. None if it does not exist or is not theirs.

    Both cases return None on purpose: callers must not be able to tell an
    id that exists from one that belongs to another user.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = %s AND user_id = %s",
            (conversation_id, user_id),
        ).fetchone()
        if not row:
            return None

        session = _isoformat_temporals(row)
        # jsonb comes back already decoded; NULL becomes an empty list.
        session["vocabulary"] = session.get("vocabulary") or []

        session["mistake_types"] = conn.execute(
            """
            SELECT mistake_type, COUNT(*) as count
            FROM grammar_feedback
            WHERE conversation_id = %s
            GROUP BY mistake_type
            ORDER BY count DESC
            """,
            (conversation_id,),
        ).fetchall()
        return session


def create_user(email: str, password_hash: str, display_name: str) -> int:
    """Insert a user account. Returns the new user id."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO users (email, password_hash, display_name, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (email, password_hash, display_name, now),
        ).fetchone()
        return row["id"]


def get_user_by_email(email: str) -> dict | None:
    """Look up a user by email. Includes password_hash for credential checks. None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, email, password_hash, display_name, created_at
            FROM users
            WHERE email = %s
            """,
            (email,),
        ).fetchone()
    return _isoformat_temporals(row) if row else None


def record_auth_attempt(ip: str, email: str) -> int:
    """Increment today's (ip, email) auth attempt counter and return the new count.

    Persistent, per-(ip, email) counter keyed on the current UTC date — a
    restart-safe backstop behind the in-memory per-IP slowapi limiter, aimed
    at credential-stuffing runs that stay under the per-minute burst limit.
    """
    window_date = datetime.now(timezone.utc).date().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO auth_attempts (ip, email, window_date, count)
            VALUES (%s, %s, %s, 1)
            ON CONFLICT (ip, email, window_date) DO UPDATE SET count = auth_attempts.count + 1
            RETURNING count
            """,
            (ip, email, window_date),
        ).fetchone()
        return row["count"]


def get_user_by_id(user_id: int) -> dict | None:
    """Look up a user by id. Excludes password_hash — profile fields only. None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, email, display_name, created_at
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        ).fetchone()
    return _isoformat_temporals(row) if row else None


def increment_daily_message_count(user_id: int) -> int:
    """Increment today's message count for user_id and return the new count."""
    usage_date = datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO daily_usage (user_id, usage_date, message_count, voice_call_count, updated_at)
            VALUES (%s, %s, 1, 0, %s)
            ON CONFLICT (user_id, usage_date) DO UPDATE SET
                message_count = daily_usage.message_count + 1,
                updated_at = excluded.updated_at
            RETURNING message_count
            """,
            (user_id, usage_date, now),
        ).fetchone()
        return row["message_count"]


def increment_daily_voice_call_count(user_id: int) -> int:
    """Increment today's voice-call count for user_id and return the new count."""
    usage_date = datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO daily_usage (user_id, usage_date, message_count, voice_call_count, updated_at)
            VALUES (%s, %s, 0, 1, %s)
            ON CONFLICT (user_id, usage_date) DO UPDATE SET
                voice_call_count = daily_usage.voice_call_count + 1,
                updated_at = excluded.updated_at
            RETURNING voice_call_count
            """,
            (user_id, usage_date, now),
        ).fetchone()
        return row["voice_call_count"]


def get_daily_usage(user_id: int) -> dict:
    """Return today's message/voice-call counts for user_id (zeros if no activity yet)."""
    usage_date = datetime.now(timezone.utc).date().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT message_count, voice_call_count FROM daily_usage "
            "WHERE user_id = %s AND usage_date = %s",
            (user_id, usage_date),
        ).fetchone()
    return {
        "message_count": row["message_count"] if row else 0,
        "voice_call_count": row["voice_call_count"] if row else 0,
    }
