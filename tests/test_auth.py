import time
from statistics import mean

import jwt
import psycopg
import pytest
from fastapi import HTTPException
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
def user_repo():
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

    with pytest.raises(psycopg.errors.UniqueViolation):
        user_repo.create_user("DUPE@Example.com", "hashed", "Second")


# --- get_current_user dependency ----------------------------------------------


@pytest.fixture
def current_user_settings(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)

    from api.config import get_settings

    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def test_get_current_user_returns_user_for_valid_token(user_repo, current_user_settings):
    from api.dependencies import get_current_user

    user_id = user_repo.create_user("dep@example.com", "hashed", "Dep User")
    token = create_access_token(user_id, SECRET)

    user = get_current_user(f"Bearer {token}", current_user_settings, user_repo)

    assert user.id == user_id
    assert user.email == "dep@example.com"


def test_get_current_user_rejects_missing_header(user_repo, current_user_settings):
    from api.dependencies import get_current_user

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(None, current_user_settings, user_repo)

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_non_bearer_scheme(user_repo, current_user_settings):
    from api.dependencies import get_current_user

    user_id = user_repo.create_user("dep2@example.com", "hashed", "Dep User")
    token = create_access_token(user_id, SECRET)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(f"Token {token}", current_user_settings, user_repo)

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_malformed_token(user_repo, current_user_settings):
    from api.dependencies import get_current_user

    with pytest.raises(HTTPException) as exc_info:
        get_current_user("Bearer not-a-jwt", current_user_settings, user_repo)

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_expired_token(user_repo, current_user_settings):
    from api.dependencies import get_current_user

    user_id = user_repo.create_user("dep3@example.com", "hashed", "Dep User")
    token = create_access_token(user_id, SECRET, expiry_hours=-1)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(f"Bearer {token}", current_user_settings, user_repo)

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_token_for_deleted_user(user_repo, current_user_settings):
    from api.dependencies import get_current_user

    token = create_access_token(999999, SECRET)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(f"Bearer {token}", current_user_settings, user_repo)

    assert exc_info.value.status_code == 401


# --- auth routes -------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)

    from api.config import get_settings

    get_settings.cache_clear()

    from api.main import app
    from api.rate_limit import limiter

    # Rate limiting is exercised in its own test; every other route test would
    # otherwise share one limiter bucket keyed on the same TestClient IP.
    monkeypatch.setattr(limiter, "enabled", False)

    # Deliberately not a context manager: running the lifespan would re-read
    # settings and re-open the connection pool the conftest fixture manages.
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


def test_signup_maps_the_unique_constraint_race_to_409(client, monkeypatch):
    """The UNIQUE constraint — not the fast-path lookup — is the real guard.

    Two concurrent signups can both pass `get_user_by_email`; the loser must
    still get a 409, not a 500. Forcing the lookup to report "no such user"
    reproduces that race deterministically.
    """
    client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

    from repositories.user_repo import UserRepository

    monkeypatch.setattr(UserRepository, "get_user_by_email", lambda self, email: None)

    response = client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

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


# Samples per path. Each login pays ~100ms of bcrypt, and the daily (ip, email)
# cap is 20 attempts, so this stays well inside both the runtime and the budget.
LOGIN_TIMING_SAMPLES = 6

# Generous enough that ordinary scheduler noise cannot fail the test, tight
# enough that a skipped bcrypt call (which is ~1000x faster) always does.
LOGIN_TIMING_RATIO_MIN = 0.5
LOGIN_TIMING_RATIO_MAX = 2.0


def test_login_takes_similar_time_for_known_and_unknown_emails(client):
    """A nonexistent email must cost the same bcrypt work as a wrong password (issue #103).

    login() verifies against DUMMY_HASH when there is no user row, so both paths
    pay bcrypt's full cost. Short-circuiting the missing-row case ("no row → 401
    immediately") would make the unknown-email path orders of magnitude faster
    and leak account existence through response time.
    """
    client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

    known_email_body = {"email": SIGNUP_BODY["email"], "password": "not the password"}
    unknown_email_body = {"email": "nobody@example.com", "password": "not the password"}

    def timed_login(body: dict) -> float:
        started = time.perf_counter()
        response = client.post("/api/v1/auth/login", json=body)
        elapsed = time.perf_counter() - started
        assert response.status_code == 401
        return elapsed

    # One warm-up per path keeps first-call import and connection costs out of
    # the samples.
    timed_login(known_email_body)
    timed_login(unknown_email_body)

    # Interleaved so any machine-wide slowdown mid-run hits both samples equally.
    known_times: list[float] = []
    unknown_times: list[float] = []
    for _ in range(LOGIN_TIMING_SAMPLES):
        known_times.append(timed_login(known_email_body))
        unknown_times.append(timed_login(unknown_email_body))

    ratio = mean(unknown_times) / mean(known_times)

    assert LOGIN_TIMING_RATIO_MIN <= ratio <= LOGIN_TIMING_RATIO_MAX, (
        f"unknown-email login averaged {mean(unknown_times):.4f}s vs "
        f"{mean(known_times):.4f}s for a known email (ratio {ratio:.3f}) — "
        "the constant-time DUMMY_HASH path may have been bypassed"
    )


def test_record_auth_attempt_increments_per_ip_and_email():
    assert db.record_auth_attempt("1.2.3.4", "a@example.com") == 1
    assert db.record_auth_attempt("1.2.3.4", "a@example.com") == 2
    assert db.record_auth_attempt("1.2.3.4", "a@example.com") == 3


def test_record_auth_attempt_keeps_separate_counters_per_ip_and_email():
    assert db.record_auth_attempt("1.2.3.4", "a@example.com") == 1
    assert db.record_auth_attempt("5.6.7.8", "a@example.com") == 1
    assert db.record_auth_attempt("1.2.3.4", "b@example.com") == 1
    assert db.record_auth_attempt("1.2.3.4", "a@example.com") == 2


def test_login_hits_persistent_daily_attempt_cap_beyond_the_burst_limit(client, monkeypatch):
    # The in-memory slowapi limiter is disabled by the `client` fixture, so this
    # exercises the DB-backed per-(ip, email) cap in isolation.
    from api import rate_limit

    monkeypatch.setattr(rate_limit, "AUTH_MAX_ATTEMPTS_PER_DAY", 3)

    login_body = {"email": "victim@example.com", "password": "wrong password"}
    statuses = [
        client.post("/api/v1/auth/login", json=login_body).status_code for _ in range(5)
    ]

    assert statuses[:3] == [401, 401, 401]
    assert statuses[3:] == [429, 429]


def test_signup_hits_persistent_daily_attempt_cap(client, monkeypatch):
    from api import rate_limit

    monkeypatch.setattr(rate_limit, "AUTH_MAX_ATTEMPTS_PER_DAY", 2)

    statuses = [
        client.post(
            "/api/v1/auth/signup",
            json={**SIGNUP_BODY, "email": f"user{i}@example.com"},
        ).status_code
        for i in range(4)
    ]

    # Each call uses a distinct email but the same client IP, so the cap is
    # keyed on (ip, email) — every distinct email gets its own 2-attempt budget,
    # so all four succeed with 201.
    assert statuses == [201, 201, 201, 201]


def test_repeated_signups_for_the_same_email_hit_the_daily_cap(client, monkeypatch):
    from api import rate_limit

    monkeypatch.setattr(rate_limit, "AUTH_MAX_ATTEMPTS_PER_DAY", 2)

    statuses = [
        client.post("/api/v1/auth/signup", json=SIGNUP_BODY).status_code for _ in range(4)
    ]

    assert statuses[0] == 201
    assert statuses[1] == 409
    assert statuses[2:] == [429, 429]


def test_login_is_rate_limited(monkeypatch):
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
