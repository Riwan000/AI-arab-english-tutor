"""End-of-session performance summary."""

import streamlit as st

from services.scoring import calculate_session_summary


def render_summary() -> None:
    st.header("Session Summary")

    summary = calculate_session_summary(
        messages=st.session_state.messages,
        mistakes=st.session_state.mistakes,
    )
    st.session_state.score = summary

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
        for key in ("messages", "mistakes", "vocabulary", "score"):
            st.session_state[key] = [] if key != "score" else {}
        st.session_state.conversation_started = False
        st.session_state.session_ended = False
        st.rerun()
