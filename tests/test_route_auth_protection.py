"""Chat and session routes must require auth; lessons/health must stay public."""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret")

from api.main import app  # noqa: E402 (secret must be set before import)

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
