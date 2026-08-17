"""Phase 9 exit verification â€” issues #159-#163.

HTTP-level regression coverage on top of the existing service/route/frontend
unit tests (test_voice_service.py, test_route_voice.py, test_api_client_voice.py,
test_chat_voice_input.py): these exercise the real FastAPI routes end to end
against a real (temp) database, the same TestClient pattern as
test_phase6_exit.py/test_phase7_exit.py, so a regression in the
metering/route wiring would be caught even if the lower-level unit tests --
which patch further down the stack -- still pass. The voice provider itself
stays mocked (services.voice.transcribe_audio/synthesize_speech): these tests
verify our own multipart/metering/response plumbing, not the provider's API.
"""

import os

import pytest
from fastapi.testclient import TestClient

SECRET = "test-only-secret"
os.environ.setdefault("JWT_SECRET_KEY", SECRET)

from api.main import app  # noqa: E402 (secret must be set before import)
from services import openrouter  # noqa: E402
from services import voice  # noqa: E402

# A genuine (tiny, silent) WAV file -- RIFF/WAVE header plus an empty data
# chunk -- rather than an arbitrary byte string. #159 asks to verify the
# multipart-upload path with "a sample WAV"; Deepgram is mocked below so the
# audio is never decoded, but this proves the route/UploadFile plumbing
# accepts real WAV framing, not just any bytes.
SAMPLE_WAV = (
    b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt "
    + (16).to_bytes(4, "little")
    + (1).to_bytes(2, "little")  # PCM
    + (1).to_bytes(2, "little")  # mono
    + (16000).to_bytes(4, "little")  # sample rate
    + (32000).to_bytes(4, "little")  # byte rate
    + (2).to_bytes(2, "little")  # block align
    + (16).to_bytes(2, "little")  # bits per sample
    + b"data" + (0).to_bytes(4, "little")
)

# A raw LLM turn that grammar.extract_feedback() parses into one correction
# with a non-empty arabic_explanation, so #163's round trip exercises a real
# correction card, not an empty-feedback shortcut.
LLM_REPLY_WITH_CORRECTION = """Good try! Let's fix one small thing.
```json
{"corrections": [{
    "mistake_type": "tense",
    "wrong_text": "I go yesterday",
    "correct_text": "I went yesterday",
    "english_explanation": "Use past tense for completed actions.",
    "arabic_explanation": "Ø§Ø³ØªØ®Ø¯Ù… Ø§Ù„Ù…Ø§Ø¶ÙŠ Ù‡Ù†Ø§",
    "tip": "Remember -ed endings"
}]}
```"""


@pytest.fixture
def voice_calls():
    """Captures the arguments services.voice's real functions were called
    with, so tests can prove the request bytes/text actually reached the
    service layer instead of just asserting a mock's canned return value."""
    return {}


@pytest.fixture
def scoped_client(monkeypatch, voice_calls):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)

    def fake_transcribe(audio_bytes, mimetype):
        voice_calls["transcribe"] = (audio_bytes, mimetype)
        return "hello teacher", "en"

    def fake_synthesize(text, language):
        voice_calls["synthesize"] = (text, language)
        return b"ID3-fake-mp3-bytes"

    monkeypatch.setattr(voice, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(voice, "synthesize_speech", fake_synthesize)
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: "Great job!")

    from api.config import get_settings

    get_settings.cache_clear()

    from api.rate_limit import limiter

    monkeypatch.setattr(limiter, "enabled", False)

    yield TestClient(app)

    get_settings.cache_clear()


def _signup(scoped_client, email: str) -> dict:
    response = scoped_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct horse battery staple", "display_name": "Learner"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _transcribe(scoped_client, headers):
    return scoped_client.post(
        "/api/v1/voice/transcribe",
        headers=headers,
        files={"audio": ("sample.wav", SAMPLE_WAV, "audio/wav")},
    )


def _speak(scoped_client, headers, text: str = "hello"):
    return scoped_client.post(
        "/api/v1/voice/speak",
        headers=headers,
        json={"text": text, "language": "en"},
    )


def _send_text_message(scoped_client, headers, text: str = "hi"):
    return scoped_client.post(
        "/api/v1/chat/message",
        headers=headers,
        json={"lesson_id": None, "mode": "free_talk", "messages": [{"role": "user", "content": text}]},
    )


# --- #159: multipart-upload a sample WAV, confirm the correct text is returned ---


def test_transcribe_accepts_a_real_wav_upload_and_returns_the_transcript(scoped_client, voice_calls):
    headers = _signup(scoped_client, "phase9-159@example.com")

    response = _transcribe(scoped_client, headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"text": "hello teacher", "language": "en"}
    # Proves the multipart bytes actually reached the service layer intact,
    # not just that the route returns whatever the mock is told to return.
    sent_bytes, sent_mimetype = voice_calls["transcribe"]
    assert sent_bytes == SAMPLE_WAV
    assert sent_mimetype == "audio/wav"


# --- #160: /voice/speak returns playable audio bytes -----------------------


def test_speak_returns_playable_audio_bytes(scoped_client, voice_calls):
    headers = _signup(scoped_client, "phase9-160@example.com")

    response = _speak(scoped_client, headers, "Great job!")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"ID3-fake-mp3-bytes"
    assert len(response.content) > 0
    # Proves the requested text and language actually reached the service
    # layer, not just that the route echoes a mock.
    assert voice_calls["synthesize"] == ("Great job!", "en")


# --- #161: voice daily limit is independent of the text limit --------------


def test_voice_limit_hit_blocks_both_transcribe_and_speak_with_a_clear_429(
    scoped_client, monkeypatch
):
    headers = _signup(scoped_client, "phase9-161a@example.com")
    monkeypatch.setenv("DAILY_VOICE_CALL_LIMIT", "1")

    from api.config import get_settings

    get_settings.cache_clear()

    first = _speak(scoped_client, headers)
    assert first.status_code == 200, first.text

    blocked_speak = _speak(scoped_client, headers)
    assert blocked_speak.status_code == 429, blocked_speak.text
    speak_detail = blocked_speak.json()["detail"]
    assert speak_detail["kind"] == "voice"
    assert speak_detail["message"]  # Arabic-first message, non-empty

    blocked_transcribe = _transcribe(scoped_client, headers)
    assert blocked_transcribe.status_code == 429, blocked_transcribe.text
    transcribe_detail = blocked_transcribe.json()["detail"]
    assert transcribe_detail["kind"] == "voice"

    get_settings.cache_clear()


def test_exhausting_the_message_limit_does_not_block_voice_calls(scoped_client, monkeypatch):
    headers = _signup(scoped_client, "phase9-161b@example.com")
    monkeypatch.setenv("DAILY_MESSAGE_LIMIT", "1")

    from api.config import get_settings

    get_settings.cache_clear()

    assert _send_text_message(scoped_client, headers, "hi").status_code == 200
    blocked = _send_text_message(scoped_client, headers, "should be blocked")
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["kind"] == "message"

    # The text-message quota is exhausted, but voice is a separate counter.
    assert _speak(scoped_client, headers).status_code == 200
    assert _transcribe(scoped_client, headers).status_code == 200

    get_settings.cache_clear()


def test_exhausting_the_voice_limit_does_not_block_text_messages(scoped_client, monkeypatch):
    headers = _signup(scoped_client, "phase9-161c@example.com")
    monkeypatch.setenv("DAILY_VOICE_CALL_LIMIT", "1")

    from api.config import get_settings

    get_settings.cache_clear()

    assert _speak(scoped_client, headers).status_code == 200
    assert _speak(scoped_client, headers).status_code == 429

    # The voice quota is exhausted, but text messages are a separate counter.
    assert _send_text_message(scoped_client, headers, "hi").status_code == 200

    get_settings.cache_clear()


# --- #162: repeated listen taps move the voice counter, not the text counter ---


def test_repeated_speak_calls_advance_only_the_voice_counter(scoped_client, monkeypatch):
    """Simulates repeatedly tapping "listen" on a spoken reply: each tap is a
    fresh /voice/speak call. Confirms the 9.6 metering fix actually closes the
    unbounded-TTS gap -- every tap is counted, none are free, and the text
    counter never moves -- by reading the count back through the same
    GET /usage/today the frontend uses to decide when to disable the mic.
    """
    headers = _signup(scoped_client, "phase9-162@example.com")
    monkeypatch.setenv("DAILY_VOICE_CALL_LIMIT", "3")

    from api.config import get_settings

    get_settings.cache_clear()

    for _ in range(3):
        response = _speak(scoped_client, headers)
        assert response.status_code == 200, response.text

    usage = scoped_client.get("/api/v1/usage/today", headers=headers)
    assert usage.status_code == 200, usage.text
    body = usage.json()
    assert body["voice_used"] == 3
    assert body["messages_used"] == 0

    # A fourth tap past the limit is rejected, not silently unmetered.
    overflow = _speak(scoped_client, headers)
    assert overflow.status_code == 429, overflow.text

    usage_after_overflow = scoped_client.get("/api/v1/usage/today", headers=headers)
    assert usage_after_overflow.json()["messages_used"] == 0

    get_settings.cache_clear()


# --- #163: Phase 9 exit -- full voice turn works end to end ----------------


def test_full_voice_turn_record_and_reply_round_trip(scoped_client, monkeypatch):
    """Record voice -> hear reply, with a parsed Arabic correction along the
    way, per docs/VOICE_AGENT_IMPLEMENTATION_PLAN.md Â§I.

    Exercises the backend half over real HTTP routes: transcribe -> chat
    message with a parsed correction -> speak the reply. The correction
    card's listen button was intentionally removed (see
    components/correction_card.py); this test now stops at the backend
    round trip it always also covered.
    """
    headers = _signup(scoped_client, "phase9-163@example.com")
    monkeypatch.setattr(openrouter, "chat_completion", lambda messages: LLM_REPLY_WITH_CORRECTION)

    # 1. Record voice -> transcribed to text.
    transcribed = _transcribe(scoped_client, headers)
    assert transcribed.status_code == 200, transcribed.text
    user_text = transcribed.json()["text"]
    assert user_text == "hello teacher"

    # 2. Send the transcribed text as a chat message -> reply + correction.
    chat_response = _send_text_message(scoped_client, headers, user_text)
    assert chat_response.status_code == 200, chat_response.text
    chat_body = chat_response.json()
    assert chat_body["reply"]
    # The visible reply must have the ```json correction block stripped
    # (services/grammar.py:strip_json_from_response) -- it's about to be sent
    # to /voice/speak below, and a leaked JSON block would get read aloud.
    assert "```json" not in chat_body["reply"]
    assert len(chat_body["corrections"]) == 1
    correction = chat_body["corrections"][0]
    assert correction["arabic_explanation"] == "Ø§Ø³ØªØ®Ø¯Ù… Ø§Ù„Ù…Ø§Ø¶ÙŠ Ù‡Ù†Ø§"

    # 3. Hear the reply -> /voice/speak returns playable audio bytes.
    spoken = _speak(scoped_client, headers, chat_body["reply"])
    assert spoken.status_code == 200, spoken.text
    assert spoken.headers["content-type"] == "audio/mpeg"
    assert len(spoken.content) > 0
