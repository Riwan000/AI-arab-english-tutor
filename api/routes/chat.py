"""Chat endpoints."""

from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from api.schemas.chat import ChatMessageRequest, ChatStartRequest
from models.conversation import ChatResponse
from models.user import User
from services import conversation

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/start", response_model=ChatResponse)
def start_chat(
    body: ChatStartRequest,
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    return conversation.start_conversation(body.lesson_id, body.difficulty, body.mode)


@router.post("/message", response_model=ChatResponse)
def send_chat_message(
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    history, user_text = body.split_history_and_user_text()
    return conversation.send_message(body.lesson_id, history, user_text, body.difficulty, body.mode)
