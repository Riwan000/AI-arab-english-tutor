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

    _migrate_conversations_ownership_and_mode(conn)


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


_USERS_COLUMNS = "id, email, password_hash, display_name, created_at"

_USERS_TABLE_BODY = """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""


_AUTH_ATTEMPTS_TABLE_BODY = """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            email TEXT NOT NULL,
            window_date TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            UNIQUE (ip, email, window_date)
        )"""


def _ensure_accounts_schema(conn: sqlite3.Connection) -> None:
    """Create the accounts tables if absent, then apply additive account migrations.

    Runs on every connection and never drops account data — unlike the
    conversation schema, which is versioned and recreated destructively.
    """
    conn.execute(f"CREATE TABLE IF NOT EXISTS users{_USERS_TABLE_BODY};")
    conn.execute(f"CREATE TABLE IF NOT EXISTS auth_attempts{_AUTH_ATTEMPTS_TABLE_BODY};")
    _migrate_users_email_nocase(conn)


def _migrate_users_email_nocase(conn: sqlite3.Connection) -> None:
    """Schema v3: rebuild a pre-v3 users table so email compares case-insensitively.

    The app layer already lowercases before insert and lookup; NOCASE makes the
    UNIQUE constraint enforce that at the DB level too (defense in depth).
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if row is None or "NOCASE" in (row["sql"] or "").upper():
        return

    try:
        conn.executescript(f"""
            CREATE TABLE users_v3{_USERS_TABLE_BODY};
            INSERT INTO users_v3 ({_USERS_COLUMNS})
                SELECT {_USERS_COLUMNS} FROM users;
            DROP TABLE users;
            ALTER TABLE users_v3 RENAME TO users;
        """)
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        conn.execute("DROP TABLE IF EXISTS users_v3")
        conn.commit()
        raise RuntimeError(
            "Cannot apply case-insensitive email uniqueness: the users table already "
            "contains emails that differ only by case. Resolve the duplicates manually, "
            "then restart."
        ) from exc


def _migrate_conversations_ownership_and_mode(conn: sqlite3.Connection) -> None:
    """Additive-only: adds user_id/difficulty/mode to conversations and makes
    lesson_id/lesson_title nullable (Free Talk sessions have no lesson).

    Runs on every connection like `_ensure_accounts_schema`. Rebuilds the table
    to relax the NOT NULL constraints (SQLite can't ALTER that away directly),
    but always copies existing rows forward — unlike the destructive
    drop/recreate path `_needs_conversation_migration` drives for unrelated
    schema bumps, this never loses conversation history.
    """
    if not _table_exists(conn, "conversations"):
        return

    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
    }
    if {"user_id", "difficulty", "mode"}.issubset(columns):
        return

    # SQLite treats DROP TABLE on an FK parent as an implicit `DELETE FROM` for
    # the purpose of firing ON DELETE actions — with foreign_keys left ON, the
    # DROP TABLE below would cascade-delete every row in `messages` and
    # `grammar_feedback`. Disable enforcement for this rebuild only; the
    # `conversations` table itself isn't touched by DML here, just recreated
    # under the same name, so no orphaned rows are produced.
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        try:
            conn.executescript("""
                CREATE TABLE conversations_v3 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id),
                    lesson_id TEXT,
                    lesson_title TEXT,
                    difficulty TEXT,
                    mode TEXT DEFAULT 'lesson',
                    created_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    grammar_score INTEGER,
                    exchange_count INTEGER,
                    mistake_count INTEGER,
                    vocabulary TEXT,
                    recommendation TEXT,
                    model_used TEXT
                );

                INSERT INTO conversations_v3 (
                    id, lesson_id, lesson_title, created_at, ended_at,
                    grammar_score, exchange_count, mistake_count, vocabulary,
                    recommendation, model_used
                )
                SELECT id, lesson_id, lesson_title, created_at, ended_at,
                       grammar_score, exchange_count, mistake_count, vocabulary,
                       recommendation, model_used
                FROM conversations;

                DROP TABLE conversations;
                ALTER TABLE conversations_v3 RENAME TO conversations;
                CREATE INDEX IF NOT EXISTS idx_conversations_ended_at ON conversations(ended_at);
            """)
            conn.commit()
        except sqlite3.DatabaseError:
            conn.rollback()
            conn.execute("DROP TABLE IF EXISTS conversations_v3")
            conn.commit()
            raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


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
            user_id INTEGER REFERENCES users(id),
            lesson_id TEXT,
            lesson_title TEXT,
            difficulty TEXT,
            mode TEXT DEFAULT 'lesson',
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


AUTH_ATTEMPTS_RETENTION_DAYS = 2


def purge_old_auth_attempts(retention_days: int = AUTH_ATTEMPTS_RETENTION_DAYS) -> int:
    """Delete auth_attempts rows older than retention_days. Returns rows deleted.

    The counter is only ever read for today's window_date, so a couple of days
    of retention is plenty — this just keeps the table from growing unbounded
    (each distinct (ip, email, day) is its own row).
    """
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=retention_days)).isoformat()
    conn = get_connection()
    cursor = conn.execute("DELETE FROM auth_attempts WHERE window_date < ?", (cutoff,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


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
    user_id: int | None = None,
    mode: str = "lesson",
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
                user_id, lesson_id, lesson_title, mode, created_at, ended_at,
                grammar_score, exchange_count, mistake_count,
                vocabulary, recommendation, model_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def list_past_sessions(limit: int = 20, *, user_id: int) -> list[dict]:
    """List the caller's own sessions, newest first.

    `user_id` is keyword-only and required so ownership filtering can never be
    skipped — or accidentally satisfied by a positional `limit`. Rows with a
    NULL `user_id` (saved before ownership existed) belong to nobody and are
    never returned.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, lesson_id, lesson_title, ended_at,
               grammar_score, exchange_count, mistake_count, recommendation
        FROM conversations
        WHERE user_id = ?
        ORDER BY ended_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_session_summary(conversation_id: int, *, user_id: int) -> dict | None:
    """Fetch one session owned by `user_id`. None if it does not exist or is not theirs.

    Both cases return None on purpose: callers must not be able to tell an
    id that exists from one that belongs to another user.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
        (conversation_id, user_id),
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


def create_user(email: str, password_hash: str, display_name: str) -> int:
    """Insert a user account. Returns the new user id."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO users (email, password_hash, display_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (email, password_hash, display_name, now),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_user_by_email(email: str) -> dict | None:
    """Look up a user by email. Includes password_hash for credential checks. None if not found."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, email, password_hash, display_name, created_at
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def record_auth_attempt(ip: str, email: str) -> int:
    """Increment today's (ip, email) auth attempt counter and return the new count.

    Persistent, per-(ip, email) counter keyed on the current UTC date — a
    restart-safe backstop behind the in-memory per-IP slowapi limiter, aimed
    at credential-stuffing runs that stay under the per-minute burst limit.
    """
    window_date = datetime.now(timezone.utc).date().isoformat()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO auth_attempts (ip, email, window_date, count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT (ip, email, window_date) DO UPDATE SET count = count + 1
            """,
            (ip, email, window_date),
        )
        conn.commit()
        row = conn.execute(
            "SELECT count FROM auth_attempts WHERE ip = ? AND email = ? AND window_date = ?",
            (ip, email, window_date),
        ).fetchone()
        return row["count"]
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict | None:
    """Look up a user by id. Excludes password_hash — profile fields only. None if not found."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, email, display_name, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None
