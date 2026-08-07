"""Chat API schemas."""

from pydantic import BaseModel, Field, field_validator

from models.conversation import ChatResponse, Message
from models.feedback import GrammarFeedback


class ChatStartRequest(BaseModel):
    lesson_id: str = Field(min_length=1)


class ChatMessageRequest(BaseModel):
    lesson_id: str = Field(min_length=1)
    messages: list[Message] = Field(min_length=1)

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
