"""services/voice.py: ElevenLabs Scribe v2 transcription and multilingual TTS."""

from types import SimpleNamespace

import pytest

from services import voice
from services.errors import VoiceSynthesisError, VoiceTranscriptionError


class _FakeSpeechToText:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = []

    def convert(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._result


class _FakeTextToSpeech:
    def __init__(self, chunks=(b"audio-", b"bytes"), error=None):
        self._chunks = chunks
        self._error = error
        self.calls = []

    def convert(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return iter(self._chunks)


class _FakeVoicesApi:
    def __init__(self, voices=(), error=None):
        self._voices = voices
        self._error = error
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return SimpleNamespace(voices=self._voices)


class _FakeClient:
    def __init__(self, stt=None, tts=None, voices_api=None):
        self.speech_to_text = stt or _FakeSpeechToText()
        self.text_to_speech = tts or _FakeTextToSpeech()
        self.voices = voices_api or _FakeVoicesApi()


# ---------------------------------------------------------------------------
# transcribe_audio
# ---------------------------------------------------------------------------

def test_transcribe_audio_returns_transcript_and_detected_language(monkeypatch):
    stt = _FakeSpeechToText(result=SimpleNamespace(text="hello there", language_code="en-US"))
    monkeypatch.setattr(voice, "client", _FakeClient(stt=stt))

    text, language = voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")

    assert (text, language) == ("hello there", "en")


def test_transcribe_audio_detects_arabic(monkeypatch):
    stt = _FakeSpeechToText(result=SimpleNamespace(text="مرحبا", language_code="ar-SA"))
    monkeypatch.setattr(voice, "client", _FakeClient(stt=stt))

    _text, language = voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")

    assert language == "ar"


def test_transcribe_audio_sends_the_audio_bytes_and_scribe_model(monkeypatch):
    stt = _FakeSpeechToText(result=SimpleNamespace(text="ok", language_code="en-US"))
    monkeypatch.setattr(voice, "client", _FakeClient(stt=stt))

    voice.transcribe_audio(b"raw-audio-bytes", "audio/webm")

    assert stt.calls == [{"file": b"raw-audio-bytes", "model_id": "scribe_v2"}]


def test_transcribe_audio_raises_without_an_api_key(monkeypatch):
    monkeypatch.setattr(voice, "client", None)

    with pytest.raises(VoiceTranscriptionError):
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")


def test_transcribe_audio_wraps_api_errors(monkeypatch):
    stt = _FakeSpeechToText(error=RuntimeError("boom"))
    monkeypatch.setattr(voice, "client", _FakeClient(stt=stt))

    with pytest.raises(VoiceTranscriptionError) as exc_info:
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")

    assert exc_info.value.status_code == 502


def test_transcribe_audio_wraps_a_response_missing_text(monkeypatch):
    stt = _FakeSpeechToText(result=SimpleNamespace(language_code="en-US"))
    monkeypatch.setattr(voice, "client", _FakeClient(stt=stt))

    with pytest.raises(VoiceTranscriptionError):
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")


def test_transcribe_audio_wraps_a_non_string_transcript(monkeypatch):
    stt = _FakeSpeechToText(result=SimpleNamespace(text=None, language_code="en-US"))
    monkeypatch.setattr(voice, "client", _FakeClient(stt=stt))

    with pytest.raises(VoiceTranscriptionError):
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")


def test_transcribe_audio_wraps_a_missing_detected_language(monkeypatch):
    stt = _FakeSpeechToText(result=SimpleNamespace(text="hello"))
    monkeypatch.setattr(voice, "client", _FakeClient(stt=stt))

    with pytest.raises(VoiceTranscriptionError):
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")


def test_transcribe_audio_wraps_an_unsupported_detected_language(monkeypatch):
    stt = _FakeSpeechToText(result=SimpleNamespace(text="bonjour", language_code="fr-FR"))
    monkeypatch.setattr(voice, "client", _FakeClient(stt=stt))

    with pytest.raises(VoiceTranscriptionError):
        voice.transcribe_audio(b"raw-audio-bytes", "audio/wav")


# ---------------------------------------------------------------------------
# get_voices
# ---------------------------------------------------------------------------

def test_get_voices_returns_the_matching_voices(monkeypatch):
    fake_voices = [SimpleNamespace(name="Aria"), SimpleNamespace(name="Sana")]
    voices_api = _FakeVoicesApi(voices=fake_voices)
    monkeypatch.setattr(voice, "client", _FakeClient(voices_api=voices_api))

    result = voice.get_voices("ar")

    assert result == fake_voices
    assert voices_api.calls == [{"language": ["ar"], "page_size": 100}]


def test_get_voices_raises_without_an_api_key(monkeypatch):
    monkeypatch.setattr(voice, "client", None)

    with pytest.raises(VoiceSynthesisError):
        voice.get_voices("en")


def test_get_voices_rejects_an_unsupported_language(monkeypatch):
    monkeypatch.setattr(voice, "client", _FakeClient())

    with pytest.raises(VoiceSynthesisError):
        voice.get_voices("fr")


def test_get_voices_wraps_api_errors(monkeypatch):
    voices_api = _FakeVoicesApi(error=RuntimeError("boom"))
    monkeypatch.setattr(voice, "client", _FakeClient(voices_api=voices_api))

    with pytest.raises(VoiceSynthesisError) as exc_info:
        voice.get_voices("en")

    assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# synthesize_speech
# ---------------------------------------------------------------------------

def test_synthesize_speech_returns_joined_audio_bytes(monkeypatch):
    tts = _FakeTextToSpeech(chunks=(b"audio-", b"bytes"))
    monkeypatch.setattr(voice, "client", _FakeClient(tts=tts))
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "voice-en-id", "ar": "voice-ar-id"})

    audio = voice.synthesize_speech("hello there", language="en")

    assert audio == b"audio-bytes"


def test_synthesize_speech_sends_the_voice_id_model_and_text(monkeypatch):
    tts = _FakeTextToSpeech()
    monkeypatch.setattr(voice, "client", _FakeClient(tts=tts))
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "voice-en-id", "ar": "voice-ar-id"})

    voice.synthesize_speech("hello there", language="en")

    assert tts.calls == [
        {"voice_id": "voice-en-id", "model_id": "eleven_multilingual_v2", "text": "hello there"}
    ]


def test_synthesize_speech_raises_without_an_api_key(monkeypatch):
    monkeypatch.setattr(voice, "client", None)

    with pytest.raises(VoiceSynthesisError):
        voice.synthesize_speech("hello")


def test_synthesize_speech_rejects_an_unsupported_language(monkeypatch):
    monkeypatch.setattr(voice, "client", _FakeClient())
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "voice-en-id", "ar": "voice-ar-id"})

    with pytest.raises(VoiceSynthesisError):
        voice.synthesize_speech("hello", language="fr")


def test_synthesize_speech_raises_when_no_voice_id_is_configured(monkeypatch):
    monkeypatch.setattr(voice, "client", _FakeClient())
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "", "ar": "voice-ar-id"})

    with pytest.raises(VoiceSynthesisError):
        voice.synthesize_speech("hello", language="en")


def test_synthesize_speech_wraps_api_errors(monkeypatch):
    tts = _FakeTextToSpeech(error=RuntimeError("boom"))
    monkeypatch.setattr(voice, "client", _FakeClient(tts=tts))
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "voice-en-id", "ar": "voice-ar-id"})

    with pytest.raises(VoiceSynthesisError) as exc_info:
        voice.synthesize_speech("hello", language="en")

    assert exc_info.value.status_code == 502
