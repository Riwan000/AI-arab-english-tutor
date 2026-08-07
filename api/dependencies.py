"""Shared FastAPI dependencies."""

from functools import lru_cache

from repositories.session_repo import SessionRepository


@lru_cache
def get_session_repository() -> SessionRepository:
    return SessionRepository()

