"""Usage API schemas."""

from pydantic import BaseModel


class UsageTodayResponse(BaseModel):
    messages_used: int
    messages_limit: int
    voice_used: int
    voice_limit: int
