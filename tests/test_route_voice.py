"""POST /voice/transcribe and /voice/speak: auth-protected, metered, ElevenLabs-backed."""

import os

import pytest
from fastapi.testclient import TestClient

SECRET = "test-only-secret"
os.environ.setdefault("JWT_SECRET_KEY", SECRET)

from api.main import app  # noqa: E402 (secret must be set before import)
from services import voice  # noqa: E402
from services.errors import VoiceSynthesisError, VoiceTranscriptionError  # noqa: E402


@pytest.fixture
def scoped_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    monkeypatch.setattr(voice, "transcribe_audio", lambda audio_bytes, mimetype: ("hello there", "en"))
    monkeypatch.setattr(voice, "synthesize_speech", lambda text, language: b"fake-audio-bytes")

    from api.config import get_settings

    get_settings.cache_clear()

    from api.rate_limit import limiter

    monkeypatch.setattr(limiter, "enabled", False)

    yield TestClient(app)

    get_settings.cache_clear()


def _signup(scoped_client, email: str = "learner@example.com") -> dict:
    response = scoped_client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": "Learner",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_transcribe_requires_authentication(scoped_client):
    response = scoped_client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("clip.wav", b"raw-bytes", "audio/wav")},
    )

    assert response.status_code == 401


def test_transcribe_returns_the_transcript_and_detected_language(scoped_client):
    headers = _signup(scoped_client)

    response = scoped_client.post(
        "/api/v1/voice/transcribe",
        headers=headers,
        files={"audio": ("clip.wav", b"raw-bytes", "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "hello there", "language": "en"}


def test_transcribe_rejects_uploads_over_the_size_cap(scoped_client, monkeypatch):
    headers = _signup(scoped_client)
    monkeypatch.setattr("api.routes.voice.MAX_AUDIO_UPLOAD_BYTES", 10)

    response = scoped_client.post(
        "/api/v1/voice/transcribe",
        headers=headers,
        files={"audio": ("clip.wav", b"raw-bytes-longer-than-ten", "audio/wav")},
    )

    assert response.status_code == 400


def test_transcribe_rejecting_an_oversized_upload_does_not_burn_the_daily_quota(
    scoped_client, monkeypatch
):
    headers = _signup(scoped_client)
    monkeypatch.setattr("api.routes.voice.MAX_AUDIO_UPLOAD_BYTES", 10)
    monkeypatch.setenv("DAILY_VOICE_CALL_LIMIT", "1")

    from api.config import get_settings

    get_settings.cache_clear()

    rejected = scoped_client.post(
        "/api/v1/voice/transcribe",
        headers=headers,
        files={"audio": ("clip.wav", b"raw-bytes-longer-than-ten", "audio/wav")},
    )
    assert rejected.status_code == 400

    accepted = scoped_client.post(
        "/api/v1/voice/speak",
        headers=headers,
        json={"text": "hello", "language": "en"},
    )
    assert accepted.status_code == 200  # quota untouched by the rejected upload

    get_settings.cache_clear()


def test_speak_rejecting_an_unsupported_language_does_not_burn_the_daily_quota(
    scoped_client, monkeypatch
):
    """SpeakRequest.language is a Literal["en", "ar"], so anything else is
    rejected by Pydantic validation (422) before the route body ever runs --
    unlike the old dead `if body.language not in {...}: raise ValueError`
    guard removed from api/routes/voice.py, this never reaches usage metering."""
    headers = _signup(scoped_client)
    monkeypatch.setenv("DAILY_VOICE_CALL_LIMIT", "1")

    from api.config import get_settings

    get_settings.cache_clear()

    rejected = scoped_client.post(
        "/api/v1/voice/speak",
        headers=headers,
        json={"text": "bonjour", "language": "fr"},
    )
    assert rejected.status_code == 422

    accepted = scoped_client.post(
        "/api/v1/voice/speak",
        headers=headers,
        json={"text": "hello", "language": "en"},
    )
    assert accepted.status_code == 200  # quota untouched by the rejected language

    get_settings.cache_clear()


def test_transcribe_propagates_deepgram_failures_as_502(scoped_client, monkeypatch):
    headers = _signup(scoped_client)

    def raise_error(audio_bytes, mimetype):
        raise VoiceTranscriptionError()

    monkeypatch.setattr(voice, "transcribe_audio", raise_error)

    response = scoped_client.post(
        "/api/v1/voice/transcribe",
        headers=headers,
        files={"audio": ("clip.wav", b"raw-bytes", "audio/wav")},
    )

    assert response.status_code == 502


def test_speak_requires_authentication(scoped_client):
    response = scoped_client.post("/api/v1/voice/speak", json={"text": "hello", "language": "en"})

    assert response.status_code == 401


def test_speak_returns_audio_bytes(scoped_client):
    headers = _signup(scoped_client)

    response = scoped_client.post(
        "/api/v1/voice/speak",
        headers=headers,
        json={"text": "hello there", "language": "en"},
    )

    assert response.status_code == 200
    assert response.content == b"fake-audio-bytes"
    assert response.headers["content-type"] == "audio/mpeg"


def test_speak_succeeds_for_arabic_since_elevenlabs_has_multilingual_voices(scoped_client):
    headers = _signup(scoped_client)

    response = scoped_client.post(
        "/api/v1/voice/speak",
        headers=headers,
        json={"text": "Ù…Ø±Ø­Ø¨Ø§", "language": "ar"},
    )

    assert response.status_code == 200
    assert response.content == b"fake-audio-bytes"


def test_speak_rejects_text_over_the_length_cap(scoped_client):
    headers = _signup(scoped_client)

    response = scoped_client.post(
        "/api/v1/voice/speak",
        headers=headers,
        json={"text": "a" * 3001, "language": "en"},
    )

    assert response.status_code == 422


def test_speak_rejects_empty_text(scoped_client):
    headers = _signup(scoped_client)

    response = scoped_client.post(
        "/api/v1/voice/speak",
        headers=headers,
        json={"text": "", "language": "en"},
    )

    assert response.status_code == 422


def test_speak_propagates_deepgram_failures_as_502(scoped_client, monkeypatch):
    headers = _signup(scoped_client)

    def raise_error(text, language):
        raise VoiceSynthesisError()

    monkeypatch.setattr(voice, "synthesize_speech", raise_error)

    response = scoped_client.post(
        "/api/v1/voice/speak",
        headers=headers,
        json={"text": "hello", "language": "en"},
    )

    assert response.status_code == 502


def test_voice_calls_are_metered_independently_of_the_daily_message_limit(scoped_client, monkeypatch):
    headers = _signup(scoped_client)
    monkeypatch.setenv("DAILY_VOICE_CALL_LIMIT", "1")

    from api.config import get_settings

    get_settings.cache_clear()

    first = scoped_client.post(
        "/api/v1/voice/speak",
        headers=headers,
        json={"text": "hello", "language": "en"},
    )
    second = scoped_client.post(
        "/api/v1/voice/speak",
        headers=headers,
        json={"text": "hello again", "language": "en"},
    )

    assert first.status_code == 200
    assert second.status_code == 429

    get_settings.cache_clear()
