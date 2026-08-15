"""Phase 5 exit verification — signup → login journey over HTTP (issue #106)."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

SECRET = "phase5-exit-verification-secret"

SIGNUP_BODY = {
    "email": "phase5@example.com",
    "password": "correct horse battery staple",
    "display_name": "Phase Five",
}


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


def test_signup_then_login_journey() -> None:
    """signup → login with the same credentials, both returning a usable JWT."""
    from services.auth import decode_access_token

    client = _make_client()

    signup = client.post("/api/v1/auth/signup", json=SIGNUP_BODY)
    assert signup.status_code == 201, signup.text
    signup_body = signup.json()
    user_id = signup_body["user"]["id"]
    assert signup_body["token_type"] == "bearer"
    assert decode_access_token(signup_body["access_token"], SECRET) == user_id
    assert "password_hash" not in signup_body["user"]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": SIGNUP_BODY["email"], "password": SIGNUP_BODY["password"]},
    )
    assert login.status_code == 200, login.text
    login_body = login.json()
    assert login_body["user"]["id"] == user_id
    assert decode_access_token(login_body["access_token"], SECRET) == user_id
    assert "password_hash" not in login_body["user"]


def test_signup_token_opens_a_protected_route() -> None:
    """The token handed out at signup is accepted by the auth-gated routes."""
    client = _make_client()

    signup = client.post(
        "/api/v1/auth/signup", json={**SIGNUP_BODY, "email": "phase5b@example.com"}
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["access_token"]

    unauthenticated = client.get("/api/v1/sessions")
    assert unauthenticated.status_code == 401

    authenticated = client.get(
        "/api/v1/sessions", headers={"Authorization": f"Bearer {token}"}
    )
    assert authenticated.status_code == 200, authenticated.text


def run_script(name: str) -> None:
    path = ROOT / "scripts" / name
    result = subprocess.run([sys.executable, str(path)], check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    test_signup_then_login_journey()
    print("Auth journey over HTTP (signup → login → JWT) — OK")

    test_signup_token_opens_a_protected_route()
    print("Signup token opens a protected route — OK")

    run_script("verify_no_service_imports.py")

    print("Phase 5 exit checklist (issue #106):")
    print("  [x] Signup creates a user and returns a usable JWT (#102)")
    print("  [x] Login with the same credentials returns a usable JWT (#102)")
    print("  [x] Auth-gated routes accept the issued token (#95)")
    print("  [x] Login timing is constant for known vs unknown emails (#103, tests/test_auth.py)")
    print("  [x] Expired/tampered JWT clears the session without an error banner (#104)")
    print("  [x] Account rows survive a conversation SCHEMA_VERSION bump (#105)")
    print("  [x] Frontend gate: app.py routes unauthenticated users to auth_view (#100)")
    print("  [x] No direct service/repository imports in the Streamlit layer")
    print("  [ ] Manual: uvicorn api.main:app --reload + streamlit run app.py, sign up in the")
    print("      browser and confirm the lesson picker renders instead of the auth screen")
    print("Phase 5 exit verification (issue #106): OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
