from repositories.usage_repo import UsageRepository
from services import database as db


def test_increment_message_count_forwards_user_id_and_returns_count(monkeypatch):
    captured = {}

    def fake_increment(user_id):
        captured["user_id"] = user_id
        return 4

    monkeypatch.setattr(db, "increment_daily_message_count", fake_increment)

    count = UsageRepository().increment_message_count(9)

    assert count == 4
    assert captured["user_id"] == 9


def test_increment_voice_call_count_forwards_user_id_and_returns_count(monkeypatch):
    captured = {}

    def fake_increment(user_id):
        captured["user_id"] = user_id
        return 2

    monkeypatch.setattr(db, "increment_daily_voice_call_count", fake_increment)

    count = UsageRepository().increment_voice_call_count(9)

    assert count == 2
    assert captured["user_id"] == 9
