import os

SECRET = "test-only-secret"
os.environ.setdefault("JWT_SECRET_KEY", SECRET)

from api.config import get_settings  # noqa: E402 (secret must be set before import)


def test_daily_limits_default_to_one_hundred(monkeypatch):
    monkeypatch.delenv("DAILY_MESSAGE_LIMIT", raising=False)
    monkeypatch.delenv("DAILY_VOICE_CALL_LIMIT", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.daily_message_limit == 100
    assert settings.daily_voice_call_limit == 100

    get_settings.cache_clear()


def test_daily_limits_are_overridable_via_env(monkeypatch):
    monkeypatch.setenv("DAILY_MESSAGE_LIMIT", "5")
    monkeypatch.setenv("DAILY_VOICE_CALL_LIMIT", "3")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.daily_message_limit == 5
    assert settings.daily_voice_call_limit == 3

    get_settings.cache_clear()
