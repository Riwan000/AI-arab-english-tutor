from dataclasses import dataclass

import pytest

from repositories.usage_repo import UsageRepository
from services import usage
from services.errors import DailyLimitExceededError


@dataclass
class _FakeSettings:
    daily_message_limit: int = 20
    daily_voice_call_limit: int = 20


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    settings = _FakeSettings()
    monkeypatch.setattr(usage, "get_settings", lambda: settings)
    return settings


def test_check_and_increment_allows_calls_under_the_limit(monkeypatch, fake_settings):
    fake_settings.daily_message_limit = 5
    monkeypatch.setattr(UsageRepository, "increment_message_count", lambda self, user_id: 3)

    usage.check_and_increment(user_id=1)  # must not raise


def test_check_and_increment_allows_the_call_that_reaches_the_limit_exactly(
    monkeypatch, fake_settings
):
    fake_settings.daily_message_limit = 5
    monkeypatch.setattr(UsageRepository, "increment_message_count", lambda self, user_id: 5)

    usage.check_and_increment(user_id=1)  # must not raise


def test_check_and_increment_raises_once_over_the_limit(monkeypatch, fake_settings):
    fake_settings.daily_message_limit = 5
    monkeypatch.setattr(UsageRepository, "increment_message_count", lambda self, user_id: 6)

    with pytest.raises(DailyLimitExceededError) as exc_info:
        usage.check_and_increment(user_id=1)

    error = exc_info.value
    assert error.status_code == 429
    assert error.detail["remaining"] == 0
    assert error.detail["message"]  # Arabic-first message is present
    assert error.detail["kind"] == "message"


def test_check_and_increment_forwards_the_user_id(monkeypatch, fake_settings):
    captured = {}

    def fake_increment(self, user_id):
        captured["user_id"] = user_id
        return 1

    monkeypatch.setattr(UsageRepository, "increment_message_count", fake_increment)

    usage.check_and_increment(user_id=42)

    assert captured["user_id"] == 42


def test_check_and_increment_voice_allows_calls_under_the_limit(monkeypatch, fake_settings):
    fake_settings.daily_voice_call_limit = 5
    monkeypatch.setattr(UsageRepository, "increment_voice_call_count", lambda self, user_id: 4)

    usage.check_and_increment_voice(user_id=1)  # must not raise


def test_check_and_increment_voice_raises_once_over_the_limit(monkeypatch, fake_settings):
    fake_settings.daily_voice_call_limit = 5
    monkeypatch.setattr(UsageRepository, "increment_voice_call_count", lambda self, user_id: 6)

    with pytest.raises(DailyLimitExceededError) as exc_info:
        usage.check_and_increment_voice(user_id=1)

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["remaining"] == 0
    assert exc_info.value.detail["kind"] == "voice"


def test_message_and_voice_limit_errors_use_different_messages(monkeypatch, fake_settings):
    fake_settings.daily_message_limit = 1
    fake_settings.daily_voice_call_limit = 1
    monkeypatch.setattr(UsageRepository, "increment_message_count", lambda self, user_id: 2)
    monkeypatch.setattr(UsageRepository, "increment_voice_call_count", lambda self, user_id: 2)

    with pytest.raises(DailyLimitExceededError) as message_exc:
        usage.check_and_increment(user_id=1)
    with pytest.raises(DailyLimitExceededError) as voice_exc:
        usage.check_and_increment_voice(user_id=1)

    assert message_exc.value.detail["message"] != voice_exc.value.detail["message"]
    assert message_exc.value.detail["kind"] != voice_exc.value.detail["kind"]
