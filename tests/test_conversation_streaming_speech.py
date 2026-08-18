"""services/conversation.py's _stream_reply_and_warm_speech: warms TTS for a
reply's first sentence while the LLM is still streaming the rest, using the
same first/rest split services.voice already uses for /voice/speak."""

import json

from services import conversation, openrouter, speech_cache, voice


def _chunked(text, size=7):
    """Split text into small pieces to simulate real token-by-token
    streaming, rather than handing the whole reply over in one delta."""
    return [text[i : i + size] for i in range(0, len(text), size)]


def _fake_stream(raw_json_chunks):
    def _stream(messages, model=None):
        return iter(raw_json_chunks)

    return _stream


def test_multi_sentence_reply_warms_first_and_rest_separately(monkeypatch):
    raw = json.dumps(
        {
            "reply": "Great try! Let's fix one small thing here.",
            "corrections": [],
            "session_ending": False,
        }
    )
    monkeypatch.setattr(openrouter, "chat_completion_stream", _fake_stream(_chunked(raw)))

    calls = []

    def fake_synthesize(text, language):
        calls.append((text, language))
        return [f"audio-for:{text}".encode()]

    monkeypatch.setattr(voice, "synthesize_speech_stream_to_list", fake_synthesize)

    response = conversation.send_message(None, [], "I go to school yesterday", mode="free_talk")

    assert response.reply == "Great try! Let's fix one small thing here."
    assert response.speech_id is not None

    entry = speech_cache.pop(response.speech_id, "en")
    assert entry is not None

    audio = b"".join(entry.audio_chunks())
    assert audio == b"audio-for:Great try!audio-for:Let's fix one small thing here."

    # The split must match services.voice.split_first_sentence exactly, so
    # /voice/speak's fallback path (unwarmed) would produce identical audio.
    assert voice.split_first_sentence("Great try! Let's fix one small thing here.") == (
        "Great try!",
        "Let's fix one small thing here.",
    )
    assert [text for text, _lang in calls] == ["Great try!", "Let's fix one small thing here."]
    assert all(lang == "en" for _text, lang in calls)


def test_single_sentence_reply_never_warms_speech(monkeypatch):
    raw = json.dumps({"reply": "Nice job overall", "corrections": [], "session_ending": False})
    monkeypatch.setattr(openrouter, "chat_completion_stream", _fake_stream(_chunked(raw)))

    def fail_synthesize(text, language):
        raise AssertionError("should not synthesize speech for a single-sentence reply")

    monkeypatch.setattr(voice, "synthesize_speech_stream_to_list", fail_synthesize)

    response = conversation.send_message(None, [], "hi", mode="free_talk")

    assert response.reply == "Nice job overall"
    assert response.speech_id is None


def test_language_is_threaded_through_to_the_warmed_synthesis_call(monkeypatch):
    raw = json.dumps({"reply": "Marhaba! Kaifa haluk today.", "corrections": []})
    monkeypatch.setattr(openrouter, "chat_completion_stream", _fake_stream(_chunked(raw)))

    calls = []
    monkeypatch.setattr(
        voice,
        "synthesize_speech_stream_to_list",
        lambda text, language: calls.append((text, language)) or [b"x"],
    )

    response = conversation.send_message(None, [], "hi", mode="free_talk", language="ar")

    assert response.speech_id is not None
    assert all(lang == "ar" for _text, lang in calls)


def test_rest_warming_uses_the_final_parsed_reply_not_the_truncated_extractor_buffer(
    monkeypatch,
):
    """A malformed \\uXXXX escape (e.g. an unpaired surrogate) makes
    ReplyTextExtractor give up decoding partway through — but Python's json
    module accepts a lone surrogate just fine, so grammar.parse_response
    still recovers the complete, correct reply text. The "rest" audio must
    be warmed from that complete text, not from the extractor's truncated
    running buffer, or the frontend would display a full reply but hear a
    shorter one."""
    raw = (
        '{"reply": "Great job! Keep going. Nice \\ud83c work here today.", '
        '"corrections": [], "session_ending": false}'
    )
    monkeypatch.setattr(openrouter, "chat_completion_stream", _fake_stream(_chunked(raw)))

    calls = []

    def fake_synthesize(text, language):
        # A lone surrogate can't round-trip through strict utf-8 — irrelevant
        # to what this test checks (conversation.py handing the *complete*
        # text to synthesis, not synthesis's own encoding behavior).
        calls.append(text)
        return [f"audio-for:{text}".encode("utf-8", "surrogatepass")]

    monkeypatch.setattr(voice, "synthesize_speech_stream_to_list", fake_synthesize)

    response = conversation.send_message(None, [], "hi", mode="free_talk")

    assert response.reply == "Great job! Keep going. Nice \ud83c work here today."
    assert response.speech_id is not None

    entry = speech_cache.pop(response.speech_id, "en")
    assert list(entry.audio_chunks()) == [
        b"audio-for:Great job!",
        "audio-for:Keep going. Nice \ud83c work here today.".encode(
            "utf-8", "surrogatepass"
        ),
    ]
    assert calls == ["Great job!", "Keep going. Nice \ud83c work here today."]


def test_start_conversation_also_warms_speech(monkeypatch):
    raw = json.dumps({"reply": "Welcome! Let's begin the lesson.", "corrections": []})
    monkeypatch.setattr(openrouter, "chat_completion_stream", _fake_stream(_chunked(raw)))
    monkeypatch.setattr(
        voice, "synthesize_speech_stream_to_list", lambda text, language: [b"chunk"]
    )

    response = conversation.start_conversation("present_simple")

    assert response.speech_id is not None
    entry = speech_cache.pop(response.speech_id, "en")
    assert entry is not None
