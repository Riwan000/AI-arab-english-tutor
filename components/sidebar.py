"""Sidebar: lesson selector, score, mistakes, vocabulary, end session."""

from datetime import datetime

import streamlit as st

from repositories.session_repo import SessionRepository
from services.lessons import get_lesson, list_lessons


def _format_date(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%b %d, %H:%M")
    except ValueError:
        return iso_timestamp[:16]


def render_past_sessions() -> None:
    repo = SessionRepository()
    sessions = repo.list_recent(limit=10)
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
            detail = repo.get_summary(session["id"])
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

        summaries = list_lessons()
        lesson_titles = {summary.title: summary.id for summary in summaries}

        selected_title = st.selectbox(
            "Choose a lesson",
            options=list(lesson_titles.keys()),
            index=0,
        )

        if selected_title:
            lesson = get_lesson(lesson_titles[selected_title])
            st.session_state.lesson = lesson.model_dump()

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
