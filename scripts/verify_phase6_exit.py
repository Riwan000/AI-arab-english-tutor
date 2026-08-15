"""Phase 6 exit verification — mode/difficulty picker to saved summary (issue #124)."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

SECRET = "phase6-exit-verification-secret"


def _make_client() -> TestClient:
    tmpdir = tempfile.mkdtemp()
    os.environ["DATABASE_PATH"] = str(Path(tmpdir) / "test.db")
    os.environ["JWT_SECRET_KEY"] = SECRET
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    os.environ["CORS_ORIGINS"] = "http://localhost:8501"

    from api.config import get_settings

    get_settings.cache_clear()

    from api.dependencies import get_session_repository, get_user_repository

    get_session_repository.cache_clear()
    get_user_repository.cache_clear()

    from api.main import app

    return TestClient(app)


def _signup(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": "Phase Six",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_free_talk_starts_without_a_lesson_id() -> None:
    """Issue #121 — Free Talk starts with no lesson_id and the agent proactively picks topics."""
    client = _make_client()
    from services import conversation

    def fail_get_lesson(lesson_id):
        raise AssertionError("lessons.get_lesson should not be called in free_talk mode")

    original_get_lesson = conversation.lessons.get_lesson
    conversation.lessons.get_lesson = fail_get_lesson
    conversation.openrouter.chat_completion = lambda messages: "What did you do this weekend?"

    try:
        headers = _signup(client, "phase6-121@example.com")
        response = client.post("/api/v1/chat/start", headers=headers, json={"mode": "free_talk"})
        assert response.status_code == 200, response.text
        assert response.json()["reply"]
    finally:
        conversation.lessons.get_lesson = original_get_lesson


def test_lesson_mode_flow_is_unaffected() -> None:
    """Issue #122 — the pre-existing lesson-constrained flow still resolves a lesson and saves it."""
    client = _make_client()
    from services import conversation

    conversation.openrouter.chat_completion = lambda messages: "Let's practice."

    headers = _signup(client, "phase6-122@example.com")

    start = client.post(
        "/api/v1/chat/start", headers=headers, json={"lesson_id": "present_simple"}
    )
    assert start.status_code == 200, start.text

    save = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "lesson_id": "present_simple",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert save.status_code == 201, save.text

    detail = client.get(f"/api/v1/sessions/{save.json()['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["lesson_id"] == "present_simple"
    assert detail.json()["lesson_title"] == "Present Simple"


def _save_session_for(user_id: int) -> int:
    from services import database as db

    return db.save_session(
        lesson={"id": "present_simple", "title": "Present Simple"},
        messages=[{"role": "user", "content": "hi"}],
        mistakes=[],
        summary={"grammar": 90, "exchanges": 1, "mistake_count": 0},
        user_id=user_id,
    )


def test_session_ownership_is_enforced_across_two_accounts() -> None:
    """Issue #123 — account A never sees account B's sessions; foreign ids 404, not 200."""
    client = _make_client()
    a_headers = _signup(client, "phase6-123-a@example.com")
    b_headers = _signup(client, "phase6-123-b@example.com")

    from services.auth import decode_access_token

    a_token = a_headers["Authorization"].split(" ")[1]
    a_id = decode_access_token(a_token, SECRET)
    b_session_id = _save_session_for(a_id)

    a_list = client.get("/api/v1/sessions", headers=a_headers)
    b_list = client.get("/api/v1/sessions", headers=b_headers)
    assert [item["id"] for item in a_list.json()["sessions"]] == [b_session_id]
    assert b_list.json()["sessions"] == []

    a_detail = client.get(f"/api/v1/sessions/{b_session_id}", headers=a_headers)
    b_detail = client.get(f"/api/v1/sessions/{b_session_id}", headers=b_headers)
    assert a_detail.status_code == 200, a_detail.text
    assert b_detail.status_code == 404, b_detail.text


def test_free_talk_journey_end_to_end() -> None:
    """Issue #124 — picker -> Free Talk conversation -> save session -> summary, full path."""
    client = _make_client()
    from services import conversation

    def fail_get_lesson(lesson_id):
        raise AssertionError("lessons.get_lesson should not be called in free_talk mode")

    original_get_lesson = conversation.lessons.get_lesson
    conversation.lessons.get_lesson = fail_get_lesson
    conversation.openrouter.chat_completion = lambda messages: (
        "Great effort!\n```json\n"
        '{"corrections": [{"mistake_type": "verb_tense", "wrong_text": "I go", '
        '"correct_text": "I went", "english_explanation": "Past tense.", '
        '"arabic_explanation": "الماضي."}]}\n```'
    )

    try:
        headers = _signup(client, "phase6-124@example.com")

        start = client.post(
            "/api/v1/chat/start",
            headers=headers,
            json={"mode": "free_talk", "difficulty": "advanced"},
        )
        assert start.status_code == 200, start.text

        message = client.post(
            "/api/v1/chat/message",
            headers=headers,
            json={
                "mode": "free_talk",
                "difficulty": "advanced",
                "messages": [{"role": "user", "content": "I go to the market yesterday."}],
            },
        )
        assert message.status_code == 200, message.text
        corrections = message.json()["corrections"]
        assert len(corrections) == 1

        save = client.post(
            "/api/v1/sessions",
            headers=headers,
            json={
                "mode": "free_talk",
                "messages": [
                    {"role": "user", "content": "I go to the market yesterday."},
                    {"role": "assistant", "content": message.json()["reply"]},
                ],
                "mistakes": corrections,
            },
        )
        assert save.status_code == 201, save.text
        session_id = save.json()["id"]
        assert save.json()["mistake_count"] == 1

        detail = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["lesson_id"] is None
        assert detail.json()["lesson_title"] == "Free Talk"
    finally:
        conversation.lessons.get_lesson = original_get_lesson


def run_script(name: str) -> None:
    path = ROOT / "scripts" / name
    result = subprocess.run([sys.executable, str(path)], check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    test_free_talk_starts_without_a_lesson_id()
    print("Free Talk starts without a lesson_id (#121) — OK")

    test_lesson_mode_flow_is_unaffected()
    print("Lesson-constrained flow unaffected (#122) — OK")

    test_session_ownership_is_enforced_across_two_accounts()
    print("Session ownership enforced across two accounts, foreign id 404s (#123) — OK")

    test_free_talk_journey_end_to_end()
    print("Picker -> Free Talk -> save -> summary, full path (#124) — OK")

    run_script("verify_no_service_imports.py")

    print("Phase 6 exit checklist (issues #121-#124):")
    print("  [x] Free Talk starts with no lesson_id, agent needs no lesson to open (#121)")
    print("  [x] Lesson mode still resolves and saves a lesson exactly as before (#122)")
    print("  [x] GET /sessions and GET /sessions/{id} are scoped to the caller (#123)")
    print("  [x] Full journey: picker -> Free Talk -> save -> summary (#124)")
    print("  [x] No direct service/repository imports in the Streamlit layer")
    print("  [ ] Manual: uvicorn api.main:app --reload + streamlit run app.py, walk the")
    print("      mode/difficulty picker -> Free Talk -> voice -> Arabic correction card ->")
    print("      End Session -> Arabic summary flow in the browser (docs §I, frontend bullet)")
    print("Phase 6 exit verification (issues #121-#124): OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
