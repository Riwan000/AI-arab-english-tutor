"""Conversation and message data models."""

from typing import Literal

from pydantic import BaseModel, Field

from models.feedback import GrammarFeedback

MAX_MESSAGE_CONTENT_LENGTH = 2000


class Message(BaseModel):
    """Chat or session message — aligns with API chat/session payloads.

    content is capped to bound per-turn LLM cost; this applies to both
    ChatMessageRequest and SessionCreateRequest since both reuse this model.
    """

    role: Literal["user", "assistant"]
    content: str = Field(max_length=MAX_MESSAGE_CONTENT_LENGTH)
    timestamp: str | None = None
    lesson_id: str | None = None
    has_correction: bool = False


class ChatResponse(BaseModel):
    """Response from POST /api/v1/chat/start and /api/v1/chat/message."""

    reply: str
    corrections: list[GrammarFeedback] = Field(default_factory=list)


class SessionSummary(BaseModel):
    """Response from POST /api/v1/sessions."""

    id: int
    grammar_score: int
    exchange_count: int
    mistake_count: int
    vocabulary: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    mistake_types: list[str] = Field(default_factory=list)


class SessionListItem(BaseModel):
    """Item in GET /api/v1/sessions list."""

    id: int
    lesson_id: str | None
    lesson_title: str
    ended_at: str
    grammar_score: int | None = None
    exchange_count: int | None = None
    mistake_count: int | None = None
    recommendation: str | None = None


class MistakeTypeCount(BaseModel):
    mistake_type: str
    count: int


class SessionDetail(SessionSummary):
    """Response from GET /api/v1/sessions/{session_id}."""

    lesson_id: str | None
    lesson_title: str
    mistake_types: list[MistakeTypeCount] = Field(default_factory=list)


class Conversation(BaseModel):
    id: int | None = None
    lesson_id: str | None
    messages: list[Message] = Field(default_factory=list)
    score: int | None = None
