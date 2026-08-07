"""Health check endpoint."""

from fastapi import APIRouter

from api.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "version": "1.0.0",
        "model": settings.default_model,
    }
