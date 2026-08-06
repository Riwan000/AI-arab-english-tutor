"""Sidebar: lesson selector, score, mistakes, vocabulary, end session."""

import json
from pathlib import Path

import streamlit as st

LESSONS_DIR = Path(__file__).parent.parent / "lessons"


def load_lessons() -> list[dict]:
    lessons = []
    for path in sorted(LESSONS_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            lessons.append(json.load(f))
    return lessons


def render_sidebar() -> None:
    with st.sidebar:
        st.title("📚 English Tutor")

        lessons = load_lessons()
        lesson_titles = {lesson["title"]: lesson for lesson in lessons}

        selected_title = st.selectbox(
            "Choose a lesson",
            options=list(lesson_titles.keys()),
            index=0,
        )

        if selected_title:
            st.session_state.lesson = lesson_titles[selected_title]

        st.divider()
        st.subheader("Progress")

        score = st.session_state.score.get("grammar", 0)
        st.metric("Grammar Score", f"{score}%")

        if st.session_state.mistakes:
            st.caption("Common mistakes")
            for mistake in st.session_state.mistakes[-5:]:
                st.write(f"• {mistake.get('mistake_type', 'Unknown')}")

        if st.session_state.vocabulary:
            st.caption("Vocabulary")
            for word in st.session_state.vocabulary[-8:]:
                st.write(f"• {word}")

        st.divider()

        if st.button("End Session", use_container_width=True):
            st.session_state.session_ended = True
            st.rerun()
