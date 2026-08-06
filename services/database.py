"""SQLite persistence for completed conversations."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "english_tutor.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            score INTEGER
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );

        CREATE TABLE IF NOT EXISTS grammar_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            mistake_type TEXT,
            wrong_text TEXT,
            corrected_text TEXT,
            english_explanation TEXT,
            arabic_explanation TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );
    """)
    conn.commit()


def save_conversation(lesson: str, messages: list[dict], score: int) -> int:
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        "INSERT INTO conversations (lesson, created_at, score) VALUES (?, ?, ?)",
        (lesson, now, score),
    )
    conversation_id = cursor.lastrowid

    for msg in messages:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, message, timestamp) VALUES (?, ?, ?, ?)",
            (conversation_id, msg["role"], msg["content"], now),
        )

    conn.commit()
    conn.close()
    return conversation_id
