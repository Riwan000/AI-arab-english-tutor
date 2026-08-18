import os
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret")
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.config import get_settings
from api.rate_limit import limiter
from services import database as db, openrouter, grammar

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

def test_draft_requires_auth(client):
    assert client.get("/api/v1/chat/draft").status_code == 401
    assert client.get("/api/v1/chat/draft", headers={"Authorization": "Bearer garbage"}).status_code == 401
    assert client.get("/api/v1/chat/draft", headers={"Authorization": "garbage"}).status_code == 401

def test_no_user_id_param_honored(client, monkeypatch):
    monkeypatch.setattr(openrouter, "chat_completion_stream", lambda m: iter(["ok"]))
    owner_h, owner_id = signup(client, "o@e.com")
    intruder_h, intruder_id = signup(client, "i@e.com")
    db.save_draft(owner_id, messages=[{"role":"user","content":"secret"}])
    # try query-param injection
    r = client.get(f"/api/v1/chat/draft?user_id={owner_id}", headers=intruder_h)
    assert r.json() is None, r.json()

def test_lesson_mode_creates_no_draft(client, monkeypatch):
    monkeypatch.setattr(openrouter, "chat_completion_stream", lambda m: iter(["ok"]))
    h, uid = signup(client, "l@e.com")
    r = client.post("/api/v1/chat/message", headers=h, json={"mode":"lesson","lesson_id":"greetings","messages":[{"role":"user","content":"hello"}]})
    print("lesson status", r.status_code, r.json())
    assert db.get_draft(uid) is None

def test_session_ending_deletes_draft(client, monkeypatch):
    monkeypatch.setattr(openrouter, "chat_completion_stream", lambda m: iter(["ok"]))
    h, uid = signup(client, "s@e.com")
    client.post("/api/v1/chat/message", headers=h, json={"mode":"free_talk","messages":[{"role":"user","content":"hello"}]})
    assert db.get_draft(uid) is not None
    r = client.post("/api/v1/chat/message", headers=h, json={"mode":"free_talk","messages":[{"role":"user","content":"ok bye"}]})
    assert r.json()["session_ending"] is True
    assert db.get_draft(uid) is None

def test_upsert_single_row(client):
    h, uid = signup(client, "u@e.com")
    for i in range(5):
        db.save_draft(uid, messages=[{"role":"user","content":str(i)}])
    with db.get_connection() as conn:
        n = conn.execute("select count(*) as c from draft_conversations where user_id=%s",(uid,)).fetchone()["c"]
    assert n == 1
    assert db.get_draft(uid)["messages"] == [{"role":"user","content":"4"}]

def test_keyword_false_positives():
    for s in ["I hope to see you at the museum next week!",
              "My father bought a new bye... ",
              "The goodbye scene in the movie made me cry",
              "I have to go to school every morning"]:
        print(repr(s), grammar.contains_farewell_keyword(s))

def test_extract_edge(client):
    for raw in ['{"reply":"x","session_ending":"true"}', '{"reply":"x","session_ending":null}', 'not json', '[1,2]', '{"reply":"x"}', '{"reply":"x","session_ending":"false"}']:
        print(repr(raw), grammar.extract_session_ending(raw))
