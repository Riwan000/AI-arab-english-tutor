import os

SECRET = "test-only-secret"
os.environ.setdefault("JWT_SECRET_KEY", SECRET)

from api.config import get_settings  # noqa: E402 (secret must be set before import)


def test_deepgram_api_key_defaults_to_empty(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.deepgram_api_key == ""

    get_settings.cache_clear()


def test_deepgram_api_key_is_overridable_via_env(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "sk-deepgram-test")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.deepgram_api_key == "sk-deepgram-test"

    get_settings.cache_clear()
