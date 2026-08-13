"""SQLite persistence for completed conversations."""

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent.parent / "database" / "english_tutor.db"
DB_PATH = Path(os.getenv("DATABASE_PATH", str(_DEFAULT_DB)))
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "5"))
SCHEMA_VERSION = 2


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    _ensure_accounts_schema(conn)

    if _needs_conversation_migration(conn):
        _drop_conversation_tables(conn)
        _create_tables(conn)
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        conn.commit()


def _needs_conversation_migration(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, "conversations"):
        return True

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
    }
    required = {
        "lesson_id", "lesson_title", "ended_at", "grammar_score",
        "exchange_count", "mistake_count", "vocabulary", "recommendation",
    }
    if not required.issubset(columns):
        return True

    if not _table_exists(conn, "schema_version"):
        return True

    row = conn.execute("SELECT version FROM schema_version").fetchone()
    return row is None or row["version"] < SCHEMA_VERSION


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _ensure_accounts_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)


def _drop_conversation_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        DROP TABLE IF EXISTS grammar_feedback;
        DROP TABLE IF EXISTS messages;
        DROP TABLE IF EXISTS conversations;
    """)


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
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

        CREATE TABLE IF NOT EXISTS messages (
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

        CREATE TABLE IF NOT EXISTS grammar_feedback (
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
    """)


def purge_old_conversations(retention_days: int = RETENTION_DAYS) -> int:
    """Delete conversations older than retention_days. Returns rows deleted."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM conversations WHERE ended_at < ?",
        (cutoff,),
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def save_session(
    lesson: dict,
    messages: list[dict],
    mistakes: list,
    summary: dict,
    model_used: str | None = None,
) -> int | None:
    """Persist a completed session. Returns conversation id or None if nothing to save."""
    if not messages:
        return None

    now = datetime.now(timezone.utc).isoformat()
    created_at = messages[0].get("timestamp", now)
    model = model_used or os.getenv("DEFAULT_MODEL", "")

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO conversations (
                lesson_id, lesson_title, created_at, ended_at,
                grammar_score, exchange_count, mistake_count,
                vocabulary, recommendation, model_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lesson["id"],
                lesson["title"],
                created_at,
                now,
                summary.get("grammar"),
                summary.get("exchanges"),
                summary.get("mistake_count"),
                json.dumps(summary.get("vocabulary", [])),
                summary.get("recommendation"),
                model,
            ),
        )
        conversation_id = cursor.lastrowid
        message_ids_by_index: dict[int, int] = {}

        for sequence, msg in enumerate(messages):
            row = conn.execute(
                """
                INSERT INTO messages (
                    conversation_id, role, content, timestamp,
                    sequence, lesson_id, has_correction
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    msg["role"],
                    msg["content"],
                    msg.get("timestamp", now),
                    sequence,
                    msg.get("lesson_id", lesson["id"]),
                    1 if msg.get("has_correction") or msg.get("feedback") else 0,
                ),
            )
            message_ids_by_index[sequence] = row.lastrowid

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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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

        conn.commit()
        return conversation_id
    finally:
        conn.close()


def list_past_sessions(limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, lesson_id, lesson_title, ended_at,
               grammar_score, exchange_count, mistake_count, recommendation
        FROM conversations
        ORDER BY ended_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_session_summary(conversation_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    if not row:
        conn.close()
        return None

    session = dict(row)
    session["vocabulary"] = json.loads(session.get("vocabulary") or "[]")

    mistakes = conn.execute(
        """
        SELECT mistake_type, COUNT(*) as count
        FROM grammar_feedback
        WHERE conversation_id = ?
        GROUP BY mistake_type
        ORDER BY count DESC
        """,
        (conversation_id,),
    ).fetchall()
    session["mistake_types"] = [dict(m) for m in mistakes]
    conn.close()
    return session
