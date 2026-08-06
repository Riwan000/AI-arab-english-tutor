"""Conversation and message data models."""

from datetime import datetime

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    lesson: str | None = None


class Conversation(BaseModel):
    id: int | None = None
    lesson: str
    messages: list[Message] = []
    score: int | None = None
