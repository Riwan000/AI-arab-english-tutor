"""Chat endpoints."""

from fastapi import APIRouter, Depends

from api.dependencies import get_current_user, get_draft_repository
from api.schemas.chat import ChatMessageRequest, ChatStartRequest
from models.conversation import ChatResponse, DraftConversation
from models.user import User
from repositories.draft_repo import DraftRepository
from services import conversation, usage

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/start", response_model=ChatResponse)
def start_chat(
    body: ChatStartRequest,
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    usage.check_and_increment(current_user.id)
    return conversation.start_conversation(
        body.lesson_id,
        body.difficulty,
        body.mode,
        user_id=current_user.id,
        language=body.language,
    )


@router.post("/message", response_model=ChatResponse)
def send_chat_message(
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    usage.check_and_increment(current_user.id)
    history, user_text = body.split_history_and_user_text()
    return conversation.send_message(
        body.lesson_id,
        history,
        user_text,
        body.difficulty,
        body.mode,
        user_id=current_user.id,
        language=body.language,
    )


@router.get("/draft", response_model=DraftConversation | None)
def get_chat_draft(
    repo: DraftRepository = Depends(get_draft_repository),
    current_user: User = Depends(get_current_user),
) -> DraftConversation | None:
    """Return the caller's in-progress free-talk conversation, or null if none exists."""
    row = repo.get(current_user.id)
    if row is None:
        return None

    return DraftConversation(
        messages=row.get("messages") or [],
        lesson_id=row.get("lesson_id"),
        mode=row.get("mode", "free_talk"),
        difficulty=row.get("difficulty"),
        updated_at=row.get("updated_at"),
    )

