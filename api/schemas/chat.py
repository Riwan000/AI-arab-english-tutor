"""Chat API schemas."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from models.conversation import ChatResponse, Message
from models.feedback import GrammarFeedback

MAX_HISTORY_MESSAGES = 100


class ChatStartRequest(BaseModel):
    lesson_id: str | None = Field(default=None, min_length=1)
    difficulty: Literal["beginner", "intermediate", "advanced"] = "beginner"
    mode: Literal["lesson", "free_talk"] = "lesson"
    # The voice language the frontend will request on its follow-up POST
    # /voice/speak call — lets the backend warm TTS in the right voice while
    # the reply is still streaming in. Defaults to "en"; a mismatched guess
    # just means /voice/speak's cache lookup misses and it synthesizes fresh,
    # exactly as if this field didn't exist.
    language: Literal["en", "ar"] = "en"


class ChatMessageRequest(BaseModel):
    lesson_id: str | None = Field(default=None, min_length=1)
    difficulty: Literal["beginner", "intermediate", "advanced"] = "beginner"
    mode: Literal["lesson", "free_talk"] = "lesson"
    language: Literal["en", "ar"] = "en"
    messages: list[Message] = Field(min_length=1, max_length=MAX_HISTORY_MESSAGES)

    @field_validator("messages")
    @classmethod
    def last_message_must_be_user(cls, messages: list[Message]) -> list[Message]:
        if messages[-1].role != "user":
            raise ValueError("last message must be from user")
        return messages

    def split_history_and_user_text(self) -> tuple[list[dict], str]:
        history = [msg.model_dump(exclude_none=True) for msg in self.messages[:-1]]
        user_text = self.messages[-1].content
        return history, user_text


# Re-export response models
ChatResponseSchema = ChatResponse
GrammarFeedbackSchema = GrammarFeedback
