"""Password hashing using bcrypt directly (not passlib — unmaintained, breaks on bcrypt >=4)."""

import bcrypt

from services.errors import PasswordTooLongError

MAX_PASSWORD_BYTES = 72


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
