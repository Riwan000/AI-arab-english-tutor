"""Daily usage endpoints."""

from fastapi import APIRouter, Depends

from api.config import Settings, get_settings
from api.dependencies import get_current_user, get_usage_repository
from api.schemas.usage import UsageTodayResponse
from models.user import User
from repositories.usage_repo import UsageRepository

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/today", response_model=UsageTodayResponse)
def get_today_usage(
    repo: UsageRepository = Depends(get_usage_repository),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> UsageTodayResponse:
    row = repo.get_today(current_user.id)
    return UsageTodayResponse(
        messages_used=row["message_count"],
        messages_limit=settings.daily_message_limit,
        voice_used=row["voice_call_count"],
        voice_limit=settings.daily_voice_call_limit,
    )
