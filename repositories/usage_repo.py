"""Repository for daily usage-limit counters."""

from services import database


class UsageRepository:
    def increment_message_count(self, user_id: int) -> int:
        """Increment today's message count for user_id. Returns the new count."""
        return database.increment_daily_message_count(user_id)

    def increment_voice_call_count(self, user_id: int) -> int:
        """Increment today's voice-call count for user_id. Returns the new count."""
        return database.increment_daily_voice_call_count(user_id)
