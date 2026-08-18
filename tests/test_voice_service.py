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

    def stream(self, **kwargs):
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
# synthesize_speech_stream
# ---------------------------------------------------------------------------
#
# synthesize_speech_stream is a generator function: calling it never runs a
# line of the body (not even the client/language validation) until the
# caller starts iterating. Every test below has to consume it (list(...) or
# next(...)) to actually exercise that code, matching how the /speak route
# pulls its first chunk to surface synthesis errors before streaming starts.

def test_synthesize_speech_stream_yields_the_audio_chunks(monkeypatch):
    tts = _FakeTextToSpeech(chunks=(b"audio-", b"bytes"))
    monkeypatch.setattr(voice, "client", _FakeClient(tts=tts))
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "voice-en-id", "ar": "voice-ar-id"})

    chunks = list(voice.synthesize_speech_stream("hello there", language="en"))

    assert chunks == [b"audio-", b"bytes"]


def test_synthesize_speech_stream_sends_the_voice_id_model_and_text(monkeypatch):
    tts = _FakeTextToSpeech()
    monkeypatch.setattr(voice, "client", _FakeClient(tts=tts))
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "voice-en-id", "ar": "voice-ar-id"})

    list(voice.synthesize_speech_stream("hello there", language="en"))

    assert tts.calls == [
        {
            "voice_id": "voice-en-id",
            "model_id": "eleven_flash_v2_5",
            "text": "hello there",
            "optimize_streaming_latency": 3,
        }
    ]


def test_synthesize_speech_stream_raises_without_an_api_key(monkeypatch):
    monkeypatch.setattr(voice, "client", None)

    with pytest.raises(VoiceSynthesisError):
        next(voice.synthesize_speech_stream("hello"))


def test_synthesize_speech_stream_rejects_an_unsupported_language(monkeypatch):
    monkeypatch.setattr(voice, "client", _FakeClient())
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "voice-en-id", "ar": "voice-ar-id"})

    with pytest.raises(VoiceSynthesisError):
        next(voice.synthesize_speech_stream("hello", language="fr"))


def test_synthesize_speech_stream_raises_when_no_voice_id_is_configured(monkeypatch):
    monkeypatch.setattr(voice, "client", _FakeClient())
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "", "ar": "voice-ar-id"})

    with pytest.raises(VoiceSynthesisError):
        next(voice.synthesize_speech_stream("hello", language="en"))


def test_synthesize_speech_stream_wraps_api_errors(monkeypatch):
    tts = _FakeTextToSpeech(error=RuntimeError("boom"))
    monkeypatch.setattr(voice, "client", _FakeClient(tts=tts))
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "voice-en-id", "ar": "voice-ar-id"})

    with pytest.raises(VoiceSynthesisError) as exc_info:
        next(voice.synthesize_speech_stream("hello", language="en"))

    assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# synthesize_speech_stream_pipelined
# ---------------------------------------------------------------------------


class _EchoTextToSpeech:
    """Echoes each call's `text` back as its audio chunk, so tests can
    verify per-sentence ordering/content without a shared fixed payload."""

    def __init__(self):
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return iter([kwargs["text"].encode()])


class _FailOnTextToSpeech:
    """Echoes text back as audio, except for one specific text that raises —
    used to prove an error in the backgrounded "rest" segment still
    propagates as VoiceSynthesisError."""

    def __init__(self, fail_text):
        self._fail_text = fail_text
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["text"] == self._fail_text:
            raise RuntimeError("boom")
        return iter([kwargs["text"].encode()])


def test_pipelined_falls_back_to_one_call_without_a_sentence_boundary(monkeypatch):
    tts = _EchoTextToSpeech()
    monkeypatch.setattr(voice, "client", _FakeClient(tts=tts))
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "voice-en-id", "ar": "voice-ar-id"})

    chunks = list(voice.synthesize_speech_stream_pipelined("hello there", language="en"))

    assert chunks == [b"hello there"]
    assert len(tts.calls) == 1


def test_pipelined_splits_and_streams_the_first_sentence_first(monkeypatch):
    tts = _EchoTextToSpeech()
    monkeypatch.setattr(voice, "client", _FakeClient(tts=tts))
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "voice-en-id", "ar": "voice-ar-id"})

    chunks = list(
        voice.synthesize_speech_stream_pipelined(
            "Good try! Let's fix one small thing.", language="en"
        )
    )

    assert chunks == [b"Good try!", b"Let's fix one small thing."]
    assert len(tts.calls) == 2


def test_pipelined_propagates_errors_from_the_backgrounded_rest_segment(monkeypatch):
    tts = _FailOnTextToSpeech(fail_text="Let's fix one small thing.")
    monkeypatch.setattr(voice, "client", _FakeClient(tts=tts))
    monkeypatch.setattr(voice, "VOICE_MAP", {"en": "voice-en-id", "ar": "voice-ar-id"})

    with pytest.raises(VoiceSynthesisError):
        list(
            voice.synthesize_speech_stream_pipelined(
                "Good try! Let's fix one small thing.", language="en"
            )
        )
