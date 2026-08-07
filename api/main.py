"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import get_settings
from api.dependencies import get_session_repository
from api.routes import chat, health, lessons, sessions
from services.errors import AppError


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.apply_to_environ()

    import services.database as database
    import services.openrouter as openrouter

    database.DB_PATH = __import__("pathlib").Path(settings.database_path)
    database.RETENTION_DAYS = settings.retention_days
    openrouter.OPENROUTER_API_KEY = settings.openrouter_api_key
    openrouter.OPENROUTER_BASE_URL = settings.openrouter_base_url
    openrouter.DEFAULT_MODEL = settings.default_model

    get_session_repository().purge_old(settings.retention_days)
    yield


app = FastAPI(
    title="AI English Tutor API",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(lessons.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
