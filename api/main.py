"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import psycopg
from slowapi.errors import RateLimitExceeded

from api.config import get_settings
from api.dependencies import get_session_repository
from api.rate_limit import limiter
from api.routes import auth, chat, health, lessons, sessions, usage, voice
from services.errors import AppError


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.apply_to_environ()

    import services.database as database
    import services.openrouter as openrouter
    import services.voice as voice_service

    database.RETENTION_DAYS = settings.retention_days
    openrouter.OPENROUTER_API_KEY = settings.openrouter_api_key
    openrouter.OPENROUTER_BASE_URL = settings.openrouter_base_url
    openrouter.DEFAULT_MODEL = settings.default_model
    voice_service.ELEVENLABS_API_KEY = settings.elevenlabs_api_key
    voice_service.client = voice_service.build_client(settings.elevenlabs_api_key)

    try:
        database.open_pool()
        get_session_repository().purge_old(settings.retention_days)
        database.purge_old_auth_attempts()
    except (OSError, psycopg.OperationalError):
        # DB unavailable at startup — health check should still pass.
        # psycopg raises OperationalError (and psycopg_pool's PoolTimeout,
        # a subclass of it) when Postgres is unreachable.
        pass

    try:
        yield
    finally:
        database.close_pool()


app = FastAPI(
    title="AI English Tutor API",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(lessons.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(usage.router, prefix="/api/v1")
app.include_router(voice.router, prefix="/api/v1")


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_request: Request, _exc: RateLimitExceeded) -> JSONResponse:
    """Keep the 429 body in the same {"detail": ...} envelope as AppError."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait a moment and try again."},
    )
