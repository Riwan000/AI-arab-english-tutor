"""Mode + difficulty picker — shown after login until both are chosen."""

import streamlit as st

MODE_LABELS = {"lesson": "Lesson", "free_talk": "Free Talk"}
DIFFICULTY_LABELS = {
    "beginner": "Beginner",
    "intermediate": "Intermediate",
    "advanced": "Advanced",
}


def render_mode_picker() -> None:
    st.header("Choose how you'd like to practice")

    mode = st.radio(
        "Mode",
        options=list(MODE_LABELS.keys()),
        format_func=lambda key: MODE_LABELS[key],
    )

    difficulty = st.radio(
        "Difficulty",
        options=list(DIFFICULTY_LABELS.keys()),
        format_func=lambda key: DIFFICULTY_LABELS[key],
    )

    if st.button("Continue", type="primary"):
        st.session_state.mode = mode
        st.session_state.difficulty = difficulty
        if mode == "free_talk":
            st.session_state.lesson = None
            st.session_state.conversation_started = True
        st.rerun()
