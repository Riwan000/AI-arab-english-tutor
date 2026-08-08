"""Phase 2 exit verification — full HTTP user journey (issue #63)."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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


def test_full_user_journey_mocked() -> None:
    """lesson → chat → correction → end session → past sessions over HTTP."""
    client = _make_client()

    with patch("services.openrouter.chat_completion") as mock_llm:
        mock_llm.return_value = "Hello! What do you usually do in the morning?"
        start = client.post("/api/v1/chat/start", json={"lesson_id": "present_simple"})
        assert start.status_code == 200
        opening = start.json()["reply"]
        assert opening

        mock_llm.return_value = (
            "Almost!\n"
            '```json\n{"corrections": [{"mistake_type": "Verb Form", '
            '"wrong_text": "I eating", "correct_text": "I eat", '
            '"english_explanation": "Use base verb.", "arabic_explanation": "a"}]}\n```'
        )
        message = client.post(
            "/api/v1/chat/message",
            json={
                "lesson_id": "present_simple",
                "messages": [
                    {"role": "assistant", "content": opening},
                    {"role": "user", "content": "I eating breakfast"},
                ],
            },
        )
        assert message.status_code == 200
        body = message.json()
        assert "```json" not in body["reply"]
        assert len(body["corrections"]) == 1
        correction = body["corrections"][0]

        lessons = client.get("/api/v1/lessons")
        assert lessons.status_code == 200
        assert len(lessons.json()["lessons"]) == 5

        detail = client.get("/api/v1/lessons/present_simple")
        assert detail.status_code == 200
        assert detail.json()["id"] == "present_simple"

        saved = client.post(
            "/api/v1/sessions",
            json={
                "lesson_id": "present_simple",
                "messages": [
                    {
                        "role": "assistant",
                        "content": opening,
                        "timestamp": "2026-08-07T01:00:00+00:00",
                    },
                    {
                        "role": "user",
                        "content": "I eating breakfast",
                        "timestamp": "2026-08-07T01:01:00+00:00",
                    },
                    {
                        "role": "assistant",
                        "content": body["reply"],
                        "timestamp": "2026-08-07T01:02:00+00:00",
                    },
                ],
                "mistakes": [
                    {
                        "mistake_type": correction["mistake_type"],
                        "wrong_text": correction["wrong_text"],
                        "correct_text": correction["correct_text"],
                        "english_explanation": correction["english_explanation"],
                        "arabic_explanation": correction["arabic_explanation"],
                        "tip": correction.get("tip", ""),
                        "message_index": 1,
                    }
                ],
            },
        )
        assert saved.status_code == 201
        session_id = saved.json()["id"]

        past = client.get("/api/v1/sessions")
        assert past.status_code == 200
        assert any(s["id"] == session_id for s in past.json()["sessions"])

        summary = client.get(f"/api/v1/sessions/{session_id}")
        assert summary.status_code == 200
        assert summary.json()["lesson_id"] == "present_simple"


def test_api_client_journey_mocked() -> None:
    """Streamlit api_client path over mocked HTTP responses."""
    import api_client

    fake_st = MagicMock()
    fake_st.secrets.get.return_value = "http://localhost:8000"

    with patch.object(api_client, "st", fake_st):
        with patch("api_client.httpx.get") as mock_get:
            with patch("api_client.httpx.post") as mock_post:
                from unittest.mock import MagicMock as MM

                health_resp = MM()
                health_resp.raise_for_status = MM()
                health_resp.json.return_value = {"status": "ok"}
                mock_get.return_value = health_resp
                assert api_client.health_check() is True

                lessons_resp = MM()
                lessons_resp.raise_for_status = MM()
                lessons_resp.json.return_value = {
                    "lessons": [{"id": "present_simple", "title": "Present Simple"}]
                }
                mock_get.return_value = lessons_resp
                assert api_client.list_lessons()[0]["id"] == "present_simple"

                chat_resp = MM()
                chat_resp.raise_for_status = MM()
                chat_resp.json.return_value = {
                    "reply": "Almost!",
                    "corrections": [{"mistake_type": "Verb Form"}],
                }
                mock_post.return_value = chat_resp
                result = api_client.send_message("present_simple", [], "I eating")
                assert result["reply"] == "Almost!"
                assert len(result["corrections"]) == 1


def run_script(name: str) -> None:
    path = ROOT / "scripts" / name
    result = subprocess.run([sys.executable, str(path)], check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    test_full_user_journey_mocked()
    print("Full API user journey (lesson → chat → correction → session → past) — OK")

    test_api_client_journey_mocked()
    print("api_client HTTP journey — OK")

    run_script("verify_no_service_imports.py")
    run_script("verify_api_client.py")
    run_script("verify_phase2.py")

    print("Phase 2 exit checklist (issue #63):")
    print("  [x] API flow over HTTP (TestClient)")
    print("  [x] api_client talks to backend endpoints")
    print("  [x] No direct service imports in Streamlit layer")
    print("  [x] No OPENROUTER_API_KEY in Streamlit secrets example")
    print("  [x] API smoke tests #59–#62 pass")
    print("  [ ] Manual: uvicorn + streamlit run together with real OPENROUTER_API_KEY")
    print("Phase 2 exit verification (issue #63): OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
