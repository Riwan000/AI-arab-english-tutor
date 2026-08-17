"""Chat and session routes must require auth and scope session data to the caller.

Lessons/health must stay public.
"""

import os

import pytest
from fastapi.testclient import TestClient

SECRET = "test-only-secret"
os.environ.setdefault("JWT_SECRET_KEY", SECRET)

from api.main import app  # noqa: E402 (secret must be set before import)
from services import database as db  # noqa: E402

client = TestClient(app)


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("post", "/api/v1/chat/start", {"lesson_id": "lesson-1"}),
        (
            "post",
            "/api/v1/chat/message",
            {
                "lesson_id": "lesson-1",
                "messages": [{"role": "user", "content": "hello"}],
            },
        ),
        (
            "post",
            "/api/v1/sessions",
            {
                "lesson_id": "lesson-1",
                "messages": [{"role": "user", "content": "hello"}],
            },
        ),
        ("get", "/api/v1/sessions", None),
        ("get", "/api/v1/sessions/1", None),
        ("get", "/api/v1/chat/draft", None),
    ],
)
def test_protected_route_rejects_missing_auth_header(method, path, json_body):
    kwargs = {"json": json_body} if json_body is not None else {}
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("post", "/api/v1/chat/start", {"lesson_id": "lesson-1"}),
        ("get", "/api/v1/sessions", None),
        ("get", "/api/v1/sessions/1", None),
    ],
)
def test_protected_route_rejects_malformed_auth_header(method, path, json_body):
    kwargs = {"json": json_body} if json_body is not None else {}
    response = getattr(client, method)(
        path, headers={"Authorization": "not-a-bearer-token"}, **kwargs
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    ["/api/v1/lessons", "/api/v1/health"],
)
def test_public_route_does_not_require_auth(path):
    response = client.get(path)
    assert response.status_code != 401


# --- session ownership (IDOR regression, issues #117/#118) --------------------


@pytest.fixture
def scoped_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)

    from api.config import get_settings

    get_settings.cache_clear()

    from api.rate_limit import limiter

    # Signing up two users per test would otherwise share one limiter bucket
    # keyed on the same TestClient IP; rate limiting has its own tests.
    monkeypatch.setattr(limiter, "enabled", False)

    # Deliberately not a context manager: running the lifespan would re-read
    # settings and re-open the connection pool the conftest fixture manages.
    yield TestClient(app)

    get_settings.cache_clear()


def _signup(scoped_client, email: str) -> tuple[dict, int]:
    """Register a user; return (auth headers, user id)."""
    response = scoped_client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": "Test User",
        },
    )
    assert response.status_code == 201
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


def _save_session_for(user_id: int) -> int:
    return db.save_session(
        lesson={"id": "present_simple", "title": "Present Simple"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
        user_id=user_id,
    )


def test_list_sessions_hides_another_users_sessions(scoped_client):
    owner_headers, owner_id = _signup(scoped_client, "owner@example.com")
    intruder_headers, _ = _signup(scoped_client, "intruder@example.com")
    session_id = _save_session_for(owner_id)

    owner_view = scoped_client.get("/api/v1/sessions", headers=owner_headers)
    intruder_view = scoped_client.get("/api/v1/sessions", headers=intruder_headers)

    assert [item["id"] for item in owner_view.json()["sessions"]] == [session_id]
    assert intruder_view.json()["sessions"] == []


def test_get_session_returns_404_for_another_users_session(scoped_client):
    owner_headers, owner_id = _signup(scoped_client, "owner@example.com")
    intruder_headers, _ = _signup(scoped_client, "intruder@example.com")
    session_id = _save_session_for(owner_id)

    owner_view = scoped_client.get(
        f"/api/v1/sessions/{session_id}", headers=owner_headers
    )
    intruder_view = scoped_client.get(
        f"/api/v1/sessions/{session_id}", headers=intruder_headers
    )

    assert owner_view.status_code == 200
    assert intruder_view.status_code == 404


def test_get_session_404s_identically_for_foreign_and_unknown_ids(scoped_client):
    """A distinguishable response would confirm which session ids exist."""
    _, owner_id = _signup(scoped_client, "owner@example.com")
    intruder_headers, _ = _signup(scoped_client, "intruder@example.com")
    session_id = _save_session_for(owner_id)

    foreign = scoped_client.get(
        f"/api/v1/sessions/{session_id}", headers=intruder_headers
    )
    unknown = scoped_client.get("/api/v1/sessions/999999", headers=intruder_headers)

    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json() == unknown.json()


def test_create_session_stores_the_authenticated_owner(scoped_client):
    owner_headers, owner_id = _signup(scoped_client, "owner@example.com")

    response = scoped_client.post(
        "/api/v1/sessions",
        headers=owner_headers,
        json={
            "lesson_id": "present_simple",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 201
    session_id = response.json()["id"]
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT user_id FROM conversations WHERE id = %s", (session_id,)
        ).fetchone()
    assert row["user_id"] == owner_id
