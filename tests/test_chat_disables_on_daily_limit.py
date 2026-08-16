"""render_chat() must disable chat_input on the very render pass where the
daily limit trips, not one rerun later (issue #135).

Real Streamlit's `st.rerun()` halts script execution immediately (it raises
internally) and restarts the script — so a call that just set
`daily_limit_reached` must call `st.rerun()` before falling through to a
`st.chat_input(...)` render that still uses the stale, pre-call value. These
tests make the mocked `st.rerun()` raise the same way, so a regression that
removes that rerun call (and lets the stale enabled input render) fails loud
instead of silently reintroducing the one-extra-submission gap.
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


def test_hitting_the_limit_on_conversation_start_reruns_before_rendering_input(monkeypatch):
    st = _fake_st()

    def fake_start_chat(**kwargs):
        st.session_state["daily_limit_reached"] = True
        return {"reply": "", "corrections": []}

    monkeypatch.setattr(chat_module.api_client, "start_chat", fake_start_chat)

    with patch.object(chat_module, "st", st):
        with pytest.raises(_Rerun):
            chat_module.render_chat()

    st.rerun.assert_called_once()
    st.chat_input.assert_not_called()


def test_hitting_the_limit_mid_conversation_reruns_before_returning(monkeypatch):
    st = _fake_st(messages=[{"role": "assistant", "content": "Hi!"}])

    def fake_send_message(**kwargs):
        st.session_state["daily_limit_reached"] = True
        return {"reply": "", "corrections": []}

    monkeypatch.setattr(chat_module.api_client, "send_message", fake_send_message)

    with patch.object(chat_module, "st", st):
        with pytest.raises(_Rerun):
            chat_module._handle_user_message("one more, past the limit", None)

    st.rerun.assert_called_once()
    # The failed user message must not be left in the transcript.
    assert st.session_state["messages"] == [{"role": "assistant", "content": "Hi!"}]


def test_a_non_limit_failure_does_not_rerun(monkeypatch):
    """A plain timeout/backend-unavailable failure must not loop-rerun the script."""
    st = _fake_st()
    monkeypatch.setattr(chat_module.api_client, "start_chat", lambda **kwargs: {"reply": ""})

    with patch.object(chat_module, "st", st):
        chat_module.render_chat()

    st.rerun.assert_not_called()
    st.chat_input.assert_called_once()
    _, kwargs = st.chat_input.call_args
    assert kwargs["disabled"] is False


def test_when_the_flag_is_already_set_input_renders_disabled_without_starting_a_conversation(
    monkeypatch,
):
    st = _fake_st(daily_limit_reached=True)
    start_chat = MagicMock()
    monkeypatch.setattr(chat_module.api_client, "start_chat", start_chat)

    with patch.object(chat_module, "st", st):
        chat_module.render_chat()

    start_chat.assert_not_called()
    _, kwargs = st.chat_input.call_args
    assert kwargs["disabled"] is True
