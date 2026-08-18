import os
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret")
import json, pytest
from fastapi.testclient import TestClient
from api.main import app
from api.config import get_settings
from api.rate_limit import limiter
from services import database as db, openrouter

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret")
    get_settings.cache_clear()
    monkeypatch.setattr(limiter, "enabled", False)
    yield TestClient(app)
    get_settings.cache_clear()

def signup(c, email):
    r = c.post("/api/v1/auth/signup", json={"email": email, "password": "correct horse battery staple", "display_name": "L"})
    b = r.json()
    return {"Authorization": f"Bearer {b['access_token']}"}, b["user"]["id"]

def test_lesson_mode_real_lesson_no_draft(client, monkeypatch):
    monkeypatch.setattr(openrouter, "chat_completion_stream", lambda m: iter(["ok"]))
    h, uid = signup(client, "l2@e.com")
    r = client.post("/api/v1/chat/message", headers=h, json={"mode":"lesson","lesson_id":"present_simple","messages":[{"role":"user","content":"hello"}]})
    print("STATUS", r.status_code, str(r.json())[:120])
    assert db.get_draft(uid) is None

def test_draft_shape_exact_keys(client, monkeypatch):
    monkeypatch.setattr(openrouter, "chat_completion_stream", lambda m: iter(["ok"]))
    h, uid = signup(client, "d@e.com")
    client.post("/api/v1/chat/message", headers=h, json={"mode":"free_talk","difficulty":"intermediate","messages":[{"role":"user","content":"hello"}]})
    body = client.get("/api/v1/chat/draft", headers=h).json()
    print("DRAFT JSON:", json.dumps(body))

def test_resume_roundtrip_long_reply(client, monkeypatch):
    long_reply = "A" * 2500
    monkeypatch.setattr(openrouter, "chat_completion_stream", lambda m: iter([long_reply]))
    h, uid = signup(client, "r@e.com")
    r1 = client.post("/api/v1/chat/message", headers=h, json={"mode":"free_talk","messages":[{"role":"user","content":"hello"}]})
    print("first send", r1.status_code)
    draft = client.get("/api/v1/chat/draft", headers=h).json()
    print("draft msg lens", [len(m["content"]) for m in draft["messages"]])
    # simulate frontend resume: setMessages(draft.messages) then send next
    monkeypatch.setattr(openrouter, "chat_completion_stream", lambda m: iter(["ok"]))
    resumed = draft["messages"] + [{"role":"user","content":"next"}]
    r2 = client.post("/api/v1/chat/message", headers=h, json={"mode":"free_talk","messages":resumed})
    print("RESUME SEND STATUS:", r2.status_code, str(r2.json())[:300])

def test_endsession_deletes_draft(client, monkeypatch):
    monkeypatch.setattr(openrouter, "chat_completion_stream", lambda m: iter(["ok"]))
    h, uid = signup(client, "e@e.com")
    client.post("/api/v1/chat/message", headers=h, json={"mode":"free_talk","messages":[{"role":"user","content":"hello"}]})
    assert db.get_draft(uid) is not None
    r = client.post("/api/v1/sessions", headers=h, json={"mode":"free_talk","messages":[{"role":"user","content":"hi"},{"role":"assistant","content":"yo"}],"mistakes":[]})
    print("END STATUS", r.status_code, str(r.json())[:150])
    print("draft after end:", db.get_draft(uid))
