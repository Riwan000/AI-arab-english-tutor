"""Sidebar: lesson selector, score, mistakes, vocabulary, end session."""

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from services.database import get_session_summary, list_past_sessions

LESSONS_DIR = Path(__file__).parent.parent / "lessons"


def load_lessons() -> list[dict]:
    lessons = []
    for path in sorted(LESSONS_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            lessons.append(json.load(f))
    return lessons


def _format_date(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%b %d, %H:%M")
    except ValueError:
        return iso_timestamp[:16]


def render_past_sessions() -> None:
    sessions = list_past_sessions(limit=10)
    if not sessions:
        st.caption("No past sessions yet.")
        return

    for session in sessions:
        label = (
            f"{session['lesson_title']} — "
            f"{session['grammar_score']}% — "
            f"{_format_date(session['ended_at'])}"
        )
        with st.expander(label):
            detail = get_session_summary(session["id"])
            if not detail:
                continue
            st.write(f"**Exchanges:** {detail['exchange_count']}")
            st.write(f"**Mistakes:** {detail['mistake_count']}")
            if detail["vocabulary"]:
                st.write(f"**Vocabulary:** {', '.join(detail['vocabulary'])}")
            if detail["mistake_types"]:
                st.write("**Mistake types:**")
                for mt in detail["mistake_types"]:
                    st.write(f"• {mt['mistake_type']} ({mt['count']})")
            if detail.get("recommendation"):
                st.info(detail["recommendation"])


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
                mistake_type = (
                    mistake.get("mistake_type")
                    if isinstance(mistake, dict)
                    else mistake.mistake_type
                )
                st.write(f"• {mistake_type or 'Unknown'}")

        if st.session_state.vocabulary:
            st.caption("Vocabulary")
            for word in st.session_state.vocabulary[-8:]:
                st.write(f"• {word}")

        st.divider()

        if st.session_state.conversation_started and not st.session_state.session_ended:
            if st.button("End Session", use_container_width=True):
                st.session_state.session_ended = True
                st.rerun()

        st.subheader("Past Sessions")
        render_past_sessions()
