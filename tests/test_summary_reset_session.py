"""`_reset_session()` must clear every piece of state that's indexed against
`st.session_state.messages`, not just the message list itself. Regression for
a bug caught in review of issue #157: `_last_played_audio_index` survived a
reset, so a voice reply in the *new* session at or below the old high-water
mark was silently skipped by components/chat.py's autoplay-once guard
(`idx > played_index`), because the new, shorter message list never grows
past the stale index.
"""

from unittest.mock import MagicMock, patch

import components.summary as summary_module


class _FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def test_reset_session_rewinds_the_played_audio_index():
    st = MagicMock()
    st.session_state = _FakeSessionState(
        {
            "messages": [{}, {}, {}],
            "mistakes": [],
            "vocabulary": [],
            "score": {},
            "conversation_started": True,
            "session_ended": True,
            "session_persisted": True,
            "saved_conversation_id": 7,
            "lesson": {"id": "l1"},
            "mode": "lesson",
            "difficulty": "beginner",
            "_last_played_audio_index": 2,
        }
    )

    with patch.object(summary_module, "st", st):
        summary_module._reset_session()

    assert st.session_state["_last_played_audio_index"] == -1
