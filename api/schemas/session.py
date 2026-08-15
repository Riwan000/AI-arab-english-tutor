"""Session API schemas."""

from pydantic import BaseModel, Field

from models.conversation import Message, SessionDetail, SessionListItem, SessionSummary
from models.feedback import GrammarFeedback


class SessionCreateRequest(BaseModel):
    lesson_id: str | None = Field(default=None, min_length=1)
    messages: list[Message] = Field(min_length=1)
    mistakes: list[GrammarFeedback] = Field(default_factory=list)


SessionSummaryResponse = SessionSummary
SessionListResponse = type(
    "SessionListResponse",
    (),
    {
        "from_items": staticmethod(
            lambda sessions: {"sessions": [s.model_dump() for s in sessions]}
        ),
    },
)


def build_session_list_response(items: list[SessionListItem]) -> dict:
    return {"sessions": [item.model_dump() for item in items]}


SessionDetailResponse = SessionDetail
