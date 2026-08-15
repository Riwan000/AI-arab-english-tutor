"""Password hashing using bcrypt directly (not passlib — unmaintained, breaks on bcrypt >=4)."""

import bcrypt
import jwt

from datetime import datetime, timedelta, timezone
from typing import Optional

from services.errors import PasswordTooLongError

MAX_PASSWORD_BYTES = 72
DEFAULT_EXPIRY_HOURS = 48
DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode("utf-8")


def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Rejects passwords over 72 bytes (bcrypt silently truncates beyond that)."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError()

    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against a bcrypt hash."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        return False

    return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))


def create_access_token(user_id: int, secret_key: str, expiry_hours: int = DEFAULT_EXPIRY_HOURS) -> str:
    """Create a JWT access token for a user."""
    payload = {"sub" : str(user_id), "exp" : datetime.now(tz=timezone.utc) + timedelta(hours=expiry_hours)}
    return jwt.encode(payload, secret_key, algorithm="HS256")

def decode_access_token(token: str, secret_key: str) -> Optional[int]:
    """Decode a JWT access token and return the user ID, or None if the token is unusable."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        # A validly-signed token with a missing or non-numeric "sub" is as unusable
        # as an invalid signature — both mean "no authenticated user".
        return None