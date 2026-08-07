"""Streamlit entry point for the AI English Tutor."""

import streamlit as st

import api_client
from components.chat import render_chat
from components.lesson_view import render_lesson_view
from components.sidebar import render_sidebar
from components.summary import render_summary


def init_session_state() -> None:
    defaults = {
        "lesson": None,
        "messages": [],
        "mistakes": [],
        "vocabulary": [],
        "score": {},
        "conversation_started": False,
        "session_ended": False,
        "session_persisted": False,
        "saved_conversation_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main() -> None:
    st.set_page_config(
        page_title="AI English Tutor",
        page_icon="📚",
        layout="wide",
    )

    init_session_state()

    if "backend_checked" not in st.session_state:
        if not api_client.health_check():
            st.warning(
                "Cannot reach the backend API. Start uvicorn "
                "(uvicorn api.main:app --reload --port 8000) and check BACKEND_URL "
                "in .streamlit/secrets.toml."
            )
        st.session_state.backend_checked = True

    render_sidebar()

    if st.session_state.session_ended:
        render_summary()
    elif st.session_state.conversation_started:
        render_chat()
    else:
        render_lesson_view()


if __name__ == "__main__":
    main()
