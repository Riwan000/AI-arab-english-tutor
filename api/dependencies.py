"""Shared FastAPI dependencies."""

from functools import lru_cache

from repositories.session_repo import SessionRepository
from repositories.user_repo import UserRepository


@lru_cache
def get_session_repository() -> SessionRepository:
    return SessionRepository()


@lru_cache
def get_user_repository() -> UserRepository:
    return UserRepository()

