"""Repository for completed session persistence."""

import os

from services import database


class SessionRepository:
    def save(
        self,
        lesson: dict,
        messages: list[dict],
        mistakes: list,
        summary: dict,
        model_used: str | None = None,
        user_id: int | None = None,
        mode: str = "lesson",
    ) -> int | None:
        model = model_used or os.getenv("DEFAULT_MODEL", "")
        return database.save_session(
            lesson=lesson,
            messages=messages,
            mistakes=mistakes,
            summary=summary,
            model_used=model,
            user_id=user_id,
            mode=mode,
        )

    def list_recent(self, limit: int = 10, *, user_id: int) -> list[dict]:
        return database.list_past_sessions(limit=limit, user_id=user_id)

    def get_summary(self, conversation_id: int, *, user_id: int) -> dict | None:
        return database.get_session_summary(conversation_id, user_id=user_id)

    def purge_old(self, retention_days: int | None = None) -> int:
        days = retention_days if retention_days is not None else database.RETENTION_DAYS
        return database.purge_old_conversations(retention_days=days)
