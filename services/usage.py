"""Daily usage-limit enforcement for text and voice interactions."""

from api.config import get_settings
from repositories.usage_repo import UsageRepository
from services.errors import DailyLimitExceededError

_MESSAGE_LIMIT_MESSAGE = "لقد وصلت إلى الحد اليومي لعدد الرسائل. حاول مرة أخرى غدًا."
_VOICE_LIMIT_MESSAGE = "لقد وصلت إلى الحد اليومي للمكالمات الصوتية. حاول مرة أخرى غدًا."


def check_and_increment(user_id: int) -> None:
    """Increment today's message count for user_id; raise once it exceeds the daily limit."""
    limit = get_settings().daily_message_limit
    count = UsageRepository().increment_message_count(user_id)
    if count > limit:
        raise DailyLimitExceededError(_MESSAGE_LIMIT_MESSAGE, remaining=max(limit - count, 0))


def check_and_increment_voice(user_id: int) -> None:
    """Increment today's voice-call count for user_id; raise once it exceeds the daily limit."""
    limit = get_settings().daily_voice_call_limit
    count = UsageRepository().increment_voice_call_count(user_id)
    if count > limit:
        raise DailyLimitExceededError(_VOICE_LIMIT_MESSAGE, remaining=max(limit - count, 0))
