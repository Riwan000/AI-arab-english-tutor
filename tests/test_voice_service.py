"""services/voice.py: Deepgram Nova-2 transcription and Aura synthesis."""

import httpx
import pytest

from services import voice
from services.errors import VoiceSynthesisError, VoiceTranscriptionError


@pytest.fixture(autouse=True)
def fake_api_key(monkeypatch):
    monkeypatch.setattr(voice, "DEEPGRAM_API_KEY", "test-key")


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, content=b""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.deepgram.com/v1/listen")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self):
        return self._json_data


def test_transcribe_audio_returns_the_transcript(monkeypatch):
    payload = {
        "results": {"channels": [{"alternatives": [{"transcript": "hello there"}]}]}
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(json_data=payload))

    text = voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")

    assert text == "hello there"


def test_transcribe_audio_sends_deepgram_headers_and_raw_body(monkeypatch):
    captured = {}

    def fake_post(url, params=None, headers=None, content=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["content"] = content
        payload = {"results": {"channels": [{"alternatives": [{"transcript": "ok"}]}]}}
        return _FakeResponse(json_data=payload)

    monkeypatch.setattr(httpx, "post", fake_post)

    voice.transcribe_audio(b"raw-audio-bytes", "audio/webm")

    assert captured["url"] == f"{voice.DEEPGRAM_BASE_URL}/listen"
    assert captured["params"] == {"model": "nova-2", "smart_format": "true"}
    assert captured["headers"]["Authorization"] == "Token test-key"
    assert captured["headers"]["Content-Type"] == "audio/webm"
    assert captured["content"] == b"raw-audio-bytes"


def test_transcribe_audio_raises_without_an_api_key(monkeypatch):
    monkeypatch.setattr(voice, "DEEPGRAM_API_KEY", "")

    with pytest.raises(VoiceTranscriptionError):
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")


def test_transcribe_audio_wraps_http_errors(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(status_code=502))

    with pytest.raises(VoiceTranscriptionError) as exc_info:
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")

    assert exc_info.value.status_code == 502


def test_transcribe_audio_wraps_timeouts(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", raise_timeout)

    with pytest.raises(VoiceTranscriptionError):
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")


def test_transcribe_audio_wraps_unexpected_response_shapes(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(json_data={}))

    with pytest.raises(VoiceTranscriptionError):
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")


def test_transcribe_audio_wraps_a_non_json_200_response(monkeypatch):
    class _NonJsonResponse(_FakeResponse):
        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _NonJsonResponse())

    with pytest.raises(VoiceTranscriptionError):
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")


def test_transcribe_audio_wraps_a_null_transcript(monkeypatch):
    payload = {"results": {"channels": [{"alternatives": [{"transcript": None}]}]}}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(json_data=payload))

    with pytest.raises(VoiceTranscriptionError):
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")


def test_transcribe_audio_wraps_a_non_list_channels_field(monkeypatch):
    payload = {"results": {"channels": "not-a-list"}}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(json_data=payload))

    with pytest.raises(VoiceTranscriptionError):
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")


def test_synthesize_speech_returns_audio_bytes(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(content=b"audio-bytes"))

    audio = voice.synthesize_speech("hello")

    assert audio == b"audio-bytes"


def test_synthesize_speech_sends_the_requested_voice_model(monkeypatch):
    captured = {}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse(content=b"audio-bytes")

    monkeypatch.setattr(httpx, "post", fake_post)

    voice.synthesize_speech("hello there", voice="aura-luna-en")

    assert captured["url"] == f"{voice.DEEPGRAM_BASE_URL}/speak"
    assert captured["params"] == {"model": "aura-luna-en"}
    assert captured["headers"]["Authorization"] == "Token test-key"
    assert captured["json"] == {"text": "hello there"}


def test_synthesize_speech_raises_without_an_api_key(monkeypatch):
    monkeypatch.setattr(voice, "DEEPGRAM_API_KEY", "")

    with pytest.raises(VoiceSynthesisError):
        voice.synthesize_speech("hello")


def test_synthesize_speech_wraps_http_errors(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(status_code=500))

    with pytest.raises(VoiceSynthesisError) as exc_info:
        voice.synthesize_speech("hello")

    assert exc_info.value.status_code == 502
