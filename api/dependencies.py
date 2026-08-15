"""Shared FastAPI dependencies."""

from functools import lru_cache

from fastapi import Depends, Header, HTTPException

from api.config import Settings, get_settings
from models.user import User
from repositories.session_repo import SessionRepository
from repositories.usage_repo import UsageRepository
from repositories.user_repo import UserRepository
from services.auth import decode_access_token

_UNAUTHENTICATED = HTTPException(
    status_code=401,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


@lru_cache
def get_session_repository() -> SessionRepository:
    return SessionRepository()


@lru_cache
def get_user_repository() -> UserRepository:
    return UserRepository()


@lru_cache
def get_usage_repository() -> UsageRepository:
    return UsageRepository()


def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    """Resolve the caller's User from a `Authorization: Bearer <jwt>` header.

    Raises 401 if the header is missing/malformed, the token is invalid or
    expired, or the token's subject no longer maps to a user.
    """
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _UNAUTHENTICATED

    user_id = decode_access_token(token, settings.jwt_secret_key)
    if user_id is None:
        raise _UNAUTHENTICATED

    row = user_repo.get_user_by_id(user_id)
    if row is None:
        raise _UNAUTHENTICATED

    return User(**row)

