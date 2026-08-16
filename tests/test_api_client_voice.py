"""api_client multipart-upload / raw-bytes-response voice helpers (issues #154, #155)."""

from unittest.mock import MagicMock, patch

import httpx

import api_client


@patch("api_client.httpx.post")
def test_transcribe_audio_sends_multipart_file(mock_post):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"text": "hello there"}
    mock_post.return_value = response

    result = api_client.transcribe_audio(b"\x00\x01fake-wav", mimetype="audio/wav")

    assert result == "hello there"
    _, kwargs = mock_post.call_args
    assert "files" in kwargs
    assert "json" not in kwargs
    field_name, (filename, content, content_type) = next(iter(kwargs["files"].items()))
    assert field_name == "audio"  # must match `audio: UploadFile = File(...)` in api/routes/voice.py
    assert content == b"\x00\x01fake-wav"
    assert content_type == "audio/wav"


@patch("api_client.httpx.post")
def test_transcribe_audio_returns_none_on_non_dict_response(mock_post):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = ["not", "a", "dict"]
    mock_post.return_value = response

    assert api_client.transcribe_audio(b"audio") is None


@patch("api_client.httpx.post")
def test_transcribe_audio_returns_none_on_timeout(mock_post):
    mock_post.side_effect = httpx.TimeoutException("timed out")

    assert api_client.transcribe_audio(b"audio") is None


@patch("api_client.httpx.post")
def test_transcribe_audio_sends_auth_header(mock_post):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"text": "hi"}
    mock_post.return_value = response

    api_client.set_auth_token("test-jwt")
    try:
        api_client.transcribe_audio(b"audio")
    finally:
        api_client.set_auth_token(None)

    _, kwargs = mock_post.call_args
    assert kwargs["headers"] == {"Authorization": "Bearer test-jwt"}


@patch("api_client.httpx.post")
def test_transcribe_audio_returns_none_and_shows_error_on_429(mock_post):
    """The multipart error path must reuse _handle_response_error, same as JSON posts
    (this is the client-side half of #152's independent voice-call metering)."""
    request = httpx.Request("POST", "http://localhost:8000/api/v1/voice/transcribe")
    detail = {"message": "voice limit reached", "remaining": 0, "kind": "voice"}
    response = httpx.Response(429, json={"detail": detail}, request=request)
    mock_post.return_value = response

    fake_st = MagicMock()
    fake_st.session_state = {}
    with patch.object(api_client, "st", fake_st):
        result = api_client.transcribe_audio(b"audio")

    assert result is None
    fake_st.error.assert_called_once_with("voice limit reached")


@patch("api_client.httpx.post")
def test_transcribe_audio_429_does_not_disable_typed_chat(mock_post):
    """A voice-limit 429 must not flip `daily_limit_reached` (issue #157 regression):
    that flag disables st.chat_input for the whole day, but the voice-call
    counter (services/usage.py: check_and_increment_voice) is independent from
    the text-message counter — a user who exhausts voice minutes can still type."""
    request = httpx.Request("POST", "http://localhost:8000/api/v1/voice/transcribe")
    detail = {"message": "voice limit reached", "remaining": 0, "kind": "voice"}
    response = httpx.Response(429, json={"detail": detail}, request=request)
    mock_post.return_value = response

    fake_st = MagicMock()
    fake_st.session_state = {}
    with patch.object(api_client, "st", fake_st):
        api_client.transcribe_audio(b"audio")

    assert "daily_limit_reached" not in fake_st.session_state


@patch("api_client.httpx.post")
def test_synthesize_speech_returns_raw_audio_bytes(mock_post):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.content = b"\xff\xfbaudio-bytes"
    mock_post.return_value = response

    result = api_client.synthesize_speech("hello", language="en")

    assert result == b"\xff\xfbaudio-bytes"
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {"text": "hello", "language": "en"}


@patch("api_client.httpx.post")
def test_synthesize_speech_defaults_to_english(mock_post):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.content = b"audio"
    mock_post.return_value = response

    api_client.synthesize_speech("hi")

    _, kwargs = mock_post.call_args
    assert kwargs["json"]["language"] == "en"


@patch("api_client.httpx.post")
def test_synthesize_speech_returns_none_on_request_error(mock_post):
    mock_post.side_effect = httpx.ConnectError("connection refused")

    assert api_client.synthesize_speech("hi") is None
