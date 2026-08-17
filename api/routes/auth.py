import psycopg

from fastapi import APIRouter, Depends, Request

from api.config import get_settings
from api.dependencies import get_user_repository
from api import rate_limit
from api.rate_limit import AUTH_RATE_LIMIT, limiter
from api.schemas.auth import TokenResponse, SignupRequest, LoginRequest
from models.user import User
from repositories.user_repo import UserRepository, public_user_fields
from services import database
from services.errors import DuplicateEmailError, InvalidCredentialsError, TooManyAttemptsError
from services import auth
from services.auth import DUMMY_HASH


router = APIRouter(prefix="/auth", tags=["auth"])


def _enforce_daily_attempt_cap(request: Request, email: str) -> None:
    """Raise TooManyAttemptsError once this (ip, email) pair exceeds the daily cap."""
    ip = request.client.host if request.client else "unknown"
    count = database.record_auth_attempt(ip, email.strip().lower())
    if count > rate_limit.AUTH_MAX_ATTEMPTS_PER_DAY:
        raise TooManyAttemptsError()


@router.post("/signup", response_model=TokenResponse, status_code=201)
@limiter.limit(AUTH_RATE_LIMIT)
def signup(
    request: Request,
    body: SignupRequest,
    settings=Depends(get_settings),
    user_repo: UserRepository = Depends(get_user_repository),
) -> TokenResponse:
    """Create a new user account and return an access token."""

    _enforce_daily_attempt_cap(request, body.email)

    # Fast path only — the UNIQUE constraint below is the real guard against
    # two concurrent signups racing past this check with the same email.
    if user_repo.get_user_by_email(body.email):
        raise DuplicateEmailError("A user with this email already exists")

    password_hash = auth.hash_password(body.password)
    try:
        user_id = user_repo.create_user(body.email, password_hash, body.display_name)
    except psycopg.errors.UniqueViolation as exc:
        raise DuplicateEmailError("A user with this email already exists") from exc

    user = user_repo.get_user_by_id(user_id)
    token = auth.create_access_token(user_id, settings.jwt_secret_key, settings.jwt_expiry_hours)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=User(**public_user_fields(user)),
    )

@router.post("/login", response_model=TokenResponse)
@limiter.limit(AUTH_RATE_LIMIT)
def login(
    request: Request,
    body: LoginRequest,
    settings=Depends(get_settings),
    user_repo: UserRepository = Depends(get_user_repository),
) -> TokenResponse:

    _enforce_daily_attempt_cap(request, body.email)

    row = user_repo.get_user_by_email(body.email)
    ok = auth.verify_password(body.password, row["password_hash"] if row else DUMMY_HASH)

    if not row or not ok:
        raise InvalidCredentialsError("Invalid email or password")

    token = auth.create_access_token(row["id"], settings.jwt_secret_key, settings.jwt_expiry_hours)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=User(**public_user_fields(row)),
    )
