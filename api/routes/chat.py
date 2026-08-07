"""Chat endpoints."""

from fastapi import APIRouter

from api.schemas.chat import ChatMessageRequest, ChatStartRequest
from models.conversation import ChatResponse
from services import conversation

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/start", response_model=ChatResponse)
def start_chat(body: ChatStartRequest) -> ChatResponse:
    return conversation.start_conversation(body.lesson_id)


@router.post("/message", response_model=ChatResponse)
def send_chat_message(body: ChatMessageRequest) -> ChatResponse:
    history, user_text = body.split_history_and_user_text()
    return conversation.send_message(body.lesson_id, history, user_text)
