"""Push-to-talk voice input (issue #157, migrated off streamlit-mic-recorder):
record -> transcribe -> same send_message() path as typed input -> spoken
reply autoplays once.
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


class _FakeUploadedFile:
    """Stand-in for the UploadedFile st.audio_input returns."""

    def __init__(self, data: bytes, file_id: str, content_type: str = "audio/wav"):
        self._data = data
        self.file_id = file_id
        self.type = content_type

    def getvalue(self) -> bytes:
        return self._data


def _fake_st(**session_state):
    st = MagicMock()
    st.session_state = _FakeSessionState(
        {
            "mode": "free_talk",
            "lesson": None,
            "messages": [],
            "mistakes": [],
            "_last_voice_file_id": None,
            **session_state,
        }
    )
    st.rerun.side_effect = _Rerun
    st.chat_input.return_value = None
    st.audio_input.return_value = None
    return st


def test_voice_input_does_nothing_when_recorder_returns_nothing(monkeypatch):
    st = _fake_st()
    transcribe = MagicMock()
    monkeypatch.setattr(chat_module.api_client, "transcribe_audio", transcribe)

    with patch.object(chat_module, "st", st):
        chat_module._handle_voice_input(None)

    transcribe.assert_not_called()


def test_voice_input_transcribes_and_reuses_the_same_send_message_path(monkeypatch):
    st = _fake_st()
    st.audio_input.return_value = _FakeUploadedFile(b"raw-audio", file_id="file-1")
    transcribe = MagicMock(return_value={"text": "hello teacher", "language": "en"})
    monkeypatch.setattr(chat_module.api_client, "transcribe_audio", transcribe)
    handle_user_message = MagicMock()
    monkeypatch.setattr(chat_module, "_handle_user_message", handle_user_message)

    with patch.object(chat_module, "st", st):
        chat_module._handle_voice_input({"id": "lesson-1"})

    transcribe.assert_called_once_with(b"raw-audio", mimetype="audio/wav")
    handle_user_message.assert_called_once_with(
        "hello teacher", {"id": "lesson-1"}, speak_reply=True
    )
    assert st.session_state["_last_voice_file_id"] == "file-1"


def test_voice_input_skips_send_when_transcription_is_empty(monkeypatch):
    st = _fake_st()
    st.audio_input.return_value = _FakeUploadedFile(b"x", file_id="file-1")
    monkeypatch.setattr(chat_module.api_client, "transcribe_audio", lambda *a, **k: None)
    handle_user_message = MagicMock()
    monkeypatch.setattr(chat_module, "_handle_user_message", handle_user_message)

    with patch.object(chat_module, "st", st):
        chat_module._handle_voice_input(None)

    handle_user_message.assert_not_called()


def test_voice_input_does_not_resend_the_same_recording_on_a_later_rerun(monkeypatch):
    """st.audio_input keeps returning the same file across reruns until the
    learner re-records — unlike mic_recorder's just_once=True, so this is now
    our own dedup responsibility."""
    st = _fake_st(_last_voice_file_id="file-1")
    st.audio_input.return_value = _FakeUploadedFile(b"raw-audio", file_id="file-1")
    transcribe = MagicMock()
    monkeypatch.setattr(chat_module.api_client, "transcribe_audio", transcribe)

    with patch.object(chat_module, "st", st):
        chat_module._handle_voice_input(None)

    transcribe.assert_not_called()


def test_render_chat_skips_the_recorder_once_the_daily_limit_is_hit():
    st = _fake_st(daily_limit_reached=True)

    with patch.object(chat_module, "st", st):
        chat_module.render_chat()

    st.audio_input.assert_not_called()


def test_speak_reply_true_marks_the_message_as_needing_audio(monkeypatch):
    st = _fake_st()
    monkeypatch.setattr(
        chat_module.api_client,
        "send_message",
        lambda **kwargs: {"reply": "Good job!", "corrections": []},
    )
    synthesize_speech = MagicMock(return_value=b"mp3-bytes")
    monkeypatch.setattr(chat_module.api_client, "synthesize_speech", synthesize_speech)

    with patch.object(chat_module, "st", st):
        with pytest.raises(_Rerun):
            chat_module._handle_user_message("hi", None, speak_reply=True)

    assert st.session_state["messages"][-1]["needs_audio"] is True
    # Synthesis is deferred to render time (see the audio-autoplay tests
    # below), not done while handling the message — that's the whole point:
    # the reply text must reach the screen before TTS starts.
    synthesize_speech.assert_not_called()


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
    assert st.session_state["messages"][-1]["needs_audio"] is False


def test_audio_reply_autoplays_only_once_across_reruns():
    """A message already covered by _last_played_audio_index must not replay
    on a later, unrelated rerun (issue #157: only the newest reply plays)."""
    st = _fake_st(
        messages=[
            {"role": "assistant", "content": "Hi", "needs_audio": True},
        ],
        _last_played_audio_index=0,
    )
    synthesize_speech = MagicMock(return_value=b"old-audio")

    with patch.object(chat_module, "st", st), patch.object(
        chat_module.api_client, "synthesize_speech", synthesize_speech
    ):
        chat_module.render_chat()

    st.audio.assert_not_called()
    synthesize_speech.assert_not_called()


def test_new_audio_reply_autoplays_and_advances_the_played_index():
    st = _fake_st(
        messages=[
            {"role": "assistant", "content": "Hi", "needs_audio": True},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Great!", "needs_audio": True},
        ],
        _last_played_audio_index=0,
    )
    synthesize_speech = MagicMock(return_value=b"new-audio")

    with patch.object(chat_module, "st", st), patch.object(
        chat_module.api_client, "synthesize_speech", synthesize_speech
    ):
        chat_module.render_chat()

    # Only the new message (idx 2) is synthesized — the already-played one
    # (idx 0) is skipped entirely, not just left unplayed.
    synthesize_speech.assert_called_once_with("Great!", "en")
    st.audio.assert_called_once_with(b"new-audio", autoplay=True)
    assert st.session_state["_last_played_audio_index"] == 2
