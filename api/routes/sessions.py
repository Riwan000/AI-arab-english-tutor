"""Session persistence and history endpoints."""

from fastapi import APIRouter, Depends, Query, status

from api.dependencies import get_current_user, get_session_repository
from api.schemas.session import SessionCreateRequest, build_session_list_response
from models.conversation import MistakeTypeCount, SessionDetail, SessionListItem, SessionSummary
from models.user import User
from repositories.session_repo import SessionRepository
from services import conversation
from services.errors import EmptySessionError, SessionNotFoundError

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionSummary, status_code=status.HTTP_201_CREATED)
def create_session(
    body: SessionCreateRequest,
    current_user: User = Depends(get_current_user),
) -> SessionSummary:
    messages = [msg.model_dump(exclude_none=True) for msg in body.messages]
    mistakes = body.mistakes
    result = conversation.end_session(body.lesson_id, messages, mistakes)
    if result is None:
        raise EmptySessionError()
    return result


@router.get("")
def list_sessions(
    limit: int = Query(default=10, ge=1, le=50),
    repo: SessionRepository = Depends(get_session_repository),
    current_user: User = Depends(get_current_user),
) -> dict:
    rows = repo.list_recent(limit=limit)
    items = [
        SessionListItem(
            id=row["id"],
            lesson_id=row["lesson_id"],
            lesson_title=row["lesson_title"],
            ended_at=row["ended_at"],
            grammar_score=row.get("grammar_score"),
            exchange_count=row.get("exchange_count"),
            mistake_count=row.get("mistake_count"),
            recommendation=row.get("recommendation"),
        )
        for row in rows
    ]
    return build_session_list_response(items)


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: int,
    repo: SessionRepository = Depends(get_session_repository),
    current_user: User = Depends(get_current_user),
) -> SessionDetail:
    row = repo.get_summary(session_id)
    if row is None:
        raise SessionNotFoundError()

    mistake_types = [
        MistakeTypeCount(
            mistake_type=item["mistake_type"],
            count=item["count"],
        )
        for item in row.get("mistake_types", [])
    ]

    return SessionDetail(
        id=row["id"],
        lesson_id=row["lesson_id"],
        lesson_title=row["lesson_title"],
        grammar_score=row.get("grammar_score") or 0,
        exchange_count=row.get("exchange_count") or 0,
        mistake_count=row.get("mistake_count") or 0,
        vocabulary=row.get("vocabulary") or [],
        recommendation=row.get("recommendation"),
        mistake_types=mistake_types,
    )
