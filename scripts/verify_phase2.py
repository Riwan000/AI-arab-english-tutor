"""API smoke tests for Phase 2 endpoints (issues #59–#62)."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient


def _make_client() -> TestClient:
    tmpdir = tempfile.mkdtemp()
    os.environ["DATABASE_PATH"] = str(Path(tmpdir) / "test.db")
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    os.environ["CORS_ORIGINS"] = "http://localhost:8501"

    from api.config import get_settings

    get_settings.cache_clear()

    from api.dependencies import get_session_repository

    get_session_repository.cache_clear()

    from api.main import app

    return TestClient(app)


def test_health() -> None:
    client = _make_client()
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"
    assert "model" in data


def test_lessons_list() -> None:
    client = _make_client()
    response = client.get("/api/v1/lessons")
    assert response.status_code == 200
    lessons = response.json()["lessons"]
    assert len(lessons) == 5
    ids = {lesson["id"] for lesson in lessons}
    assert "present_simple" in ids


def test_lesson_detail() -> None:
    client = _make_client()
    ok = client.get("/api/v1/lessons/present_simple")
    assert ok.status_code == 200
    assert ok.json()["title"] == "Present Simple"

    missing = client.get("/api/v1/lessons/not_a_lesson")
    assert missing.status_code == 404


def test_chat_start_and_message_mocked() -> None:
    client = _make_client()
    with patch("services.openrouter.chat_completion") as mock_llm:
        mock_llm.return_value = "Hello! Tell me about your routine."
        start = client.post("/api/v1/chat/start", json={"lesson_id": "present_simple"})
        assert start.status_code == 200
        assert start.json()["reply"] == "Hello! Tell me about your routine."

        mock_llm.return_value = (
            "Almost!\n"
            '```json\n{"corrections": [{"mistake_type": "Verb Form", '
            '"wrong_text": "I eating", "correct_text": "I eat", '
            '"english_explanation": "e", "arabic_explanation": "a"}]}\n```'
        )
        message = client.post(
            "/api/v1/chat/message",
            json={
                "lesson_id": "present_simple",
                "messages": [
                    {"role": "assistant", "content": "Hi"},
                    {"role": "user", "content": "I eating"},
                ],
            },
        )
        assert message.status_code == 200
        body = message.json()
        assert "```json" not in body["reply"]
        assert len(body["corrections"]) == 1


def test_sessions_crud() -> None:
    client = _make_client()
    payload = {
        "lesson_id": "present_simple",
        "messages": [
            {
                "role": "assistant",
                "content": "Hi",
                "timestamp": "2026-08-07T01:00:00+00:00",
            },
            {
                "role": "user",
                "content": "I eat breakfast",
                "timestamp": "2026-08-07T01:01:00+00:00",
            },
        ],
        "mistakes": [],
    }
    created = client.post("/api/v1/sessions", json=payload)
    assert created.status_code == 201
    session_id = created.json()["id"]
    assert session_id > 0

    listed = client.get("/api/v1/sessions")
    assert listed.status_code == 200
    assert any(s["id"] == session_id for s in listed.json()["sessions"])

    detail = client.get(f"/api/v1/sessions/{session_id}")
    assert detail.status_code == 200
    assert detail.json()["lesson_id"] == "present_simple"

    missing = client.get("/api/v1/sessions/99999")
    assert missing.status_code == 404


def test_api_client_base_url() -> None:
    from unittest.mock import MagicMock

    import api_client

    # api_client imports streamlit — mock secrets for unit test
    fake_st = MagicMock()
    fake_st.secrets.get.return_value = "http://test-backend:9000"
    with patch.object(api_client, "st", fake_st):
        assert api_client.base_url() == "http://test-backend:9000"


if __name__ == "__main__":
    test_health()
    print("Issue #59: GET /api/v1/health returns 200 — OK")

    test_lessons_list()
    print("Issue #60: GET /api/v1/lessons returns 5 lessons — OK")

    test_lesson_detail()

    test_chat_start_and_message_mocked()
    print("Issue #61: POST /chat/message returns clean reply + corrections — OK")

    test_sessions_crud()
    print("Issue #62: POST /sessions saves and returns summary — OK")

    test_api_client_base_url()
    print("Phase 2 API verification (issues #59–#62): OK")
