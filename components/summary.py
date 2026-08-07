"""End-of-session performance summary."""

import streamlit as st

from services.database import save_session
from services.openrouter import DEFAULT_MODEL
from services.scoring import calculate_session_summary


def persist_session() -> int | None:
    """Save the current session to SQLite if it has messages and is not yet persisted."""
    if st.session_state.get("session_persisted"):
        return st.session_state.get("saved_conversation_id")

    lesson = st.session_state.get("lesson")
    messages = st.session_state.get("messages", [])
    if not lesson or not messages:
        return None

    summary = st.session_state.get("score") or calculate_session_summary(
        messages=messages,
        mistakes=st.session_state.mistakes,
        lesson_title=lesson.get("title"),
    )

    conversation_id = save_session(
        lesson=lesson,
        messages=messages,
        mistakes=st.session_state.mistakes,
        summary=summary,
        model_used=DEFAULT_MODEL,
    )

    if conversation_id:
        st.session_state.session_persisted = True
        st.session_state.saved_conversation_id = conversation_id

    return conversation_id


def render_summary() -> None:
    st.header("Session Summary")

    summary = calculate_session_summary(
        messages=st.session_state.messages,
        mistakes=st.session_state.mistakes,
        lesson_title=st.session_state.lesson["title"] if st.session_state.lesson else None,
    )
    st.session_state.score = summary

    saved_id = persist_session()
    if saved_id:
        st.caption(f"Session saved (#{saved_id})")

    col1, col2, col3 = st.columns(3)
    col1.metric("Grammar Score", f"{summary['grammar']}%")
    col2.metric("Exchanges", summary["exchanges"])
    col3.metric("Mistakes", summary["mistake_count"])

    st.subheader("Vocabulary")
    if summary["vocabulary"]:
        st.write(", ".join(summary["vocabulary"]))
    else:
        st.write("No vocabulary tracked yet.")

    st.subheader("Common Mistakes")
    if summary["mistake_types"]:
        for mistake_type in summary["mistake_types"]:
            st.write(f"• {mistake_type}")
    else:
        st.write("No mistakes — great job!")

    st.subheader("Recommendation")
    lesson_title = st.session_state.lesson["title"] if st.session_state.lesson else "this lesson"
    st.info(summary.get("recommendation") or f"Practice {lesson_title} again tomorrow.")

    if st.button("Start New Session"):
        persist_session()
        _reset_session()
        st.rerun()


def _reset_session() -> None:
    for key in ("messages", "mistakes", "vocabulary", "score"):
        st.session_state[key] = [] if key != "score" else {}
    st.session_state.conversation_started = False
    st.session_state.session_ended = False
    st.session_state.session_persisted = False
    st.session_state.saved_conversation_id = None
