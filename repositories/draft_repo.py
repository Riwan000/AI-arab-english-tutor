"""Repository for in-progress (unfinished) conversation persistence."""

from services import database


class DraftRepository:
    def save(
        self,
        user_id: int,
        messages: list[dict],
        lesson_id: str | None = None,
        mode: str = "free_talk",
        difficulty: str | None = None,
    ) -> None:
        database.save_draft(
            user_id,
            messages=messages,
            lesson_id=lesson_id,
            mode=mode,
            difficulty=difficulty,
        )

    def get(self, user_id: int) -> dict | None:
        return database.get_draft(user_id)

    def delete(self, user_id: int) -> None:
        database.delete_draft(user_id)
