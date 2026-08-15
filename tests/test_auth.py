import sqlite3

import jwt
import pytest
from fastapi.testclient import TestClient

import services.database as db
from repositories.user_repo import UserRepository
from services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from services.errors import PasswordTooLongError

SECRET = "test-only-secret"
OTHER_SECRET = "a-different-test-only-secret"


def test_hash_password_returns_different_string_than_input():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_incorrect_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_hash_password_rejects_passwords_over_72_bytes():
    long_password = "a" * 73
    with pytest.raises(PasswordTooLongError):
        hash_password(long_password)


def test_hash_password_accepts_password_at_72_byte_limit():
    password = "a" * 72
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_hash_password_counts_bytes_not_characters():
    # Each "é" is 2 bytes in UTF-8, so 40 of them is 80 bytes.
    long_password = "é" * 40
    with pytest.raises(PasswordTooLongError):
        hash_password(long_password)


def test_verify_password_rejects_over_length_password_without_error():
    hashed = hash_password("a" * 72)
    assert verify_password("a" * 73, hashed) is False


# --- JWT access tokens -------------------------------------------------------


def test_access_token_round_trips_the_user_id():
    token = create_access_token(42, SECRET)
    assert decode_access_token(token, SECRET) == 42


def test_decode_rejects_token_signed_with_another_secret():
    token = create_access_token(42, SECRET)
    assert decode_access_token(token, OTHER_SECRET) is None


def test_decode_rejects_expired_token():
    token = create_access_token(42, SECRET, expiry_hours=-1)
    assert decode_access_token(token, SECRET) is None


def test_decode_rejects_malformed_token():
    assert decode_access_token("not-a-jwt", SECRET) is None


def test_decode_rejects_valid_signature_with_missing_subject():
    token = jwt.encode({"foo": "bar"}, SECRET, algorithm="HS256")
    assert decode_access_token(token, SECRET) is None


def test_decode_rejects_valid_signature_with_non_numeric_subject():
    token = jwt.encode({"sub": "not-a-number"}, SECRET, algorithm="HS256")
    assert decode_access_token(token, SECRET) is None


def test_default_token_expiry_is_within_spec_range():
    payload = jwt.decode(create_access_token(1, SECRET), SECRET, algorithms=["HS256"])
    from datetime import datetime, timezone

    hours = (
        datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        - datetime.now(tz=timezone.utc)
    ).total_seconds() / 3600
    assert 24 <= hours <= 72


# --- user repository ---------------------------------------------------------


@pytest.fixture
def user_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    return UserRepository()


def test_create_user_returns_id_and_get_user_by_id_omits_password_hash(user_repo):
    user_id = user_repo.create_user("new@example.com", "hashed", "New User")

    user = user_repo.get_user_by_id(user_id)

    assert user["id"] == user_id
    assert user["email"] == "new@example.com"
    assert user["display_name"] == "New User"
    assert "password_hash" not in user


def test_get_user_by_id_returns_none_for_unknown_id(user_repo):
    assert user_repo.get_user_by_id(9999) is None


def test_get_user_by_email_is_case_insensitive(user_repo):
    user_id = user_repo.create_user("Mixed@Example.com", "hashed", "Mixed Case")

    assert user_repo.get_user_by_email("mixed@example.com")["id"] == user_id
    assert user_repo.get_user_by_email("  MIXED@EXAMPLE.COM  ")["id"] == user_id


def test_get_user_by_email_includes_password_hash_for_credential_checks(user_repo):
    user_repo.create_user("creds@example.com", "hashed", "Creds User")

    assert user_repo.get_user_by_email("creds@example.com")["password_hash"] == "hashed"


def test_get_user_by_email_returns_none_for_unknown_email(user_repo):
    assert user_repo.get_user_by_email("nobody@example.com") is None


def test_create_user_rejects_duplicate_email_regardless_of_case(user_repo):
    user_repo.create_user("dupe@example.com", "hashed", "First")

    with pytest.raises(sqlite3.IntegrityError):
        user_repo.create_user("DUPE@Example.com", "hashed", "Second")


# --- auth routes -------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api.db")
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)

    from api.config import get_settings

    get_settings.cache_clear()

    from api.main import app
    from api.rate_limit import limiter

    # Rate limiting is exercised in its own test; every other route test would
    # otherwise share one limiter bucket keyed on the same TestClient IP.
    monkeypatch.setattr(limiter, "enabled", False)

    # Deliberately not a context manager: the lifespan would repoint
    # database.DB_PATH at the real database file.
    yield TestClient(app)

    get_settings.cache_clear()


SIGNUP_BODY = {
    "email": "user@example.com",
    "password": "correct horse battery staple",
    "display_name": "Test User",
}


def test_signup_returns_201_with_token_and_user(client):
    response = client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"], SECRET) == body["user"]["id"]
    assert body["user"]["email"] == "user@example.com"
    assert body["user"]["display_name"] == "Test User"
    assert "password_hash" not in body["user"]


def test_signup_rejects_duplicate_email_with_409(client):
    client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

    response = client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

    assert response.status_code == 409


def test_signup_rejects_duplicate_email_differing_only_by_case(client):
    client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

    response = client.post(
        "/api/v1/auth/signup", json={**SIGNUP_BODY, "email": "USER@Example.com"}
    )

    assert response.status_code == 409


def test_signup_rejects_short_password(client):
    response = client.post(
        "/api/v1/auth/signup", json={**SIGNUP_BODY, "password": "short"}
    )

    assert response.status_code == 422


def test_signup_rejects_blank_display_name(client):
    response = client.post(
        "/api/v1/auth/signup", json={**SIGNUP_BODY, "display_name": "   "}
    )

    assert response.status_code == 422


def test_login_returns_token_for_valid_credentials(client):
    client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": SIGNUP_BODY["email"], "password": SIGNUP_BODY["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert decode_access_token(body["access_token"], SECRET) == body["user"]["id"]
    assert "password_hash" not in body["user"]


def test_login_accepts_email_in_a_different_case(client):
    client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "USER@Example.com", "password": SIGNUP_BODY["password"]},
    )

    assert response.status_code == 200


def test_login_rejects_wrong_password_and_unknown_email_identically(client):
    client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": SIGNUP_BODY["email"], "password": "not the password"},
    )
    unknown_email = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": SIGNUP_BODY["password"]},
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_login_is_rate_limited(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "ratelimit.db")
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)

    from api.config import get_settings

    get_settings.cache_clear()

    from api.main import app
    from api.rate_limit import limiter

    limiter.reset()
    rate_limited_client = TestClient(app, client=("203.0.113.7", 50000))

    statuses = [
        rate_limited_client.post(
            "/api/v1/auth/login", json={"email": "a@example.com", "password": "x" * 12}
        ).status_code
        for _ in range(7)
    ]

    limiter.reset()
    get_settings.cache_clear()

    assert 429 in statuses
    assert statuses.count(401) == 5
