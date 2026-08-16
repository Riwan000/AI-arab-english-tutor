"""Push-to-talk voice input (issue #157): record -> transcribe -> same
send_message() path as typed input -> spoken reply autoplays once.
"""

from unittest.mock import MagicMock, patch

import pytest

import components.chat as chat_module


class _Rerun(Exception):
    """Stand-in for Streamlit's internal rerun-triggering exception."""


class _FakeSessionState(dict):
    """Minimal stand-in for Streamlit's SessionStateProxy: dict + attribute access."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _fake_st(**session_state):
    st = MagicMock()
    st.session_state = _FakeSessionState(
        {
            "mode": "free_talk",
            "lesson": None,
            "messages": [],
            "mistakes": [],
            **session_state,
        }
    )
    st.rerun.side_effect = _Rerun
    st.chat_input.return_value = None
    return st


def test_voice_input_does_nothing_when_recorder_returns_nothing(monkeypatch):
    st = _fake_st()
    mic_recorder = MagicMock(return_value=None)
    monkeypatch.setattr(chat_module, "mic_recorder", mic_recorder)
    transcribe = MagicMock()
    monkeypatch.setattr(chat_module.api_client, "transcribe_audio", transcribe)

    with patch.object(chat_module, "st", st):
        chat_module._handle_voice_input(None)

    transcribe.assert_not_called()


def test_voice_input_does_nothing_when_audio_has_no_bytes(monkeypatch):
    st = _fake_st()
    monkeypatch.setattr(chat_module, "mic_recorder", MagicMock(return_value={"bytes": None}))
    transcribe = MagicMock()
    monkeypatch.setattr(chat_module.api_client, "transcribe_audio", transcribe)

    with patch.object(chat_module, "st", st):
        chat_module._handle_voice_input(None)

    transcribe.assert_not_called()


def test_voice_input_transcribes_and_reuses_the_same_send_message_path(monkeypatch):
    st = _fake_st()
    audio = {"bytes": b"raw-audio", "format": "webm"}
    monkeypatch.setattr(chat_module, "mic_recorder", MagicMock(return_value=audio))
    transcribe = MagicMock(return_value="hello teacher")
    monkeypatch.setattr(chat_module.api_client, "transcribe_audio", transcribe)
    handle_user_message = MagicMock()
    monkeypatch.setattr(chat_module, "_handle_user_message", handle_user_message)

    with patch.object(chat_module, "st", st):
        chat_module._handle_voice_input({"id": "lesson-1"})

    transcribe.assert_called_once_with(b"raw-audio", mimetype="audio/webm")
    handle_user_message.assert_called_once_with(
        "hello teacher", {"id": "lesson-1"}, speak_reply=True
    )


def test_voice_input_skips_send_when_transcription_is_empty(monkeypatch):
    st = _fake_st()
    monkeypatch.setattr(
        chat_module, "mic_recorder", MagicMock(return_value={"bytes": b"x", "format": "webm"})
    )
    monkeypatch.setattr(chat_module.api_client, "transcribe_audio", lambda *a, **k: None)
    handle_user_message = MagicMock()
    monkeypatch.setattr(chat_module, "_handle_user_message", handle_user_message)

    with patch.object(chat_module, "st", st):
        chat_module._handle_voice_input(None)

    handle_user_message.assert_not_called()


def test_render_chat_skips_the_recorder_once_the_daily_limit_is_hit(monkeypatch):
    st = _fake_st(daily_limit_reached=True)
    mic_recorder = MagicMock()
    monkeypatch.setattr(chat_module, "mic_recorder", mic_recorder)

    with patch.object(chat_module, "st", st):
        chat_module.render_chat()

    mic_recorder.assert_not_called()


def test_speak_reply_true_stores_audio_bytes_on_the_assistant_message(monkeypatch):
    st = _fake_st()
    monkeypatch.setattr(
        chat_module.api_client,
        "send_message",
        lambda **kwargs: {"reply": "Good job!", "corrections": []},
    )
    monkeypatch.setattr(
        chat_module.api_client, "synthesize_speech", lambda text, lang: b"mp3-bytes"
    )

    with patch.object(chat_module, "st", st):
        with pytest.raises(_Rerun):
            chat_module._handle_user_message("hi", None, speak_reply=True)

    assert st.session_state["messages"][-1]["audio_reply"] == b"mp3-bytes"


def test_speak_reply_false_never_calls_synthesize_speech(monkeypatch):
    st = _fake_st()
    monkeypatch.setattr(
        chat_module.api_client,
        "send_message",
        lambda **kwargs: {"reply": "Good job!", "corrections": []},
    )
    synthesize_speech = MagicMock()
    monkeypatch.setattr(chat_module.api_client, "synthesize_speech", synthesize_speech)

    with patch.object(chat_module, "st", st):
        with pytest.raises(_Rerun):
            chat_module._handle_user_message("hi", None)

    synthesize_speech.assert_not_called()
    assert "audio_reply" not in st.session_state["messages"][-1]


def test_audio_reply_autoplays_only_once_across_reruns(monkeypatch):
    """A message already covered by _last_played_audio_index must not replay
    on a later, unrelated rerun (issue #157: only the newest reply plays)."""
    st = _fake_st(
        messages=[
            {"role": "assistant", "content": "Hi", "audio_reply": b"old-audio"},
        ],
        _last_played_audio_index=0,
    )
    monkeypatch.setattr(chat_module, "mic_recorder", MagicMock(return_value=None))

    with patch.object(chat_module, "st", st):
        chat_module.render_chat()

    st.audio.assert_not_called()


def test_new_audio_reply_autoplays_and_advances_the_played_index(monkeypatch):
    st = _fake_st(
        messages=[
            {"role": "assistant", "content": "Hi", "audio_reply": b"old-audio"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Great!", "audio_reply": b"new-audio"},
        ],
        _last_played_audio_index=0,
    )
    monkeypatch.setattr(chat_module, "mic_recorder", MagicMock(return_value=None))

    with patch.object(chat_module, "st", st):
        chat_module.render_chat()

    st.audio.assert_called_once_with(b"new-audio", autoplay=True)
    assert st.session_state["_last_played_audio_index"] == 2
