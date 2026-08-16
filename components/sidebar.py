"""Sidebar: lesson selector, score, mistakes, vocabulary, end session."""

from datetime import datetime

import streamlit as st

import api_client
import i18n


def _format_date(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%b %d, %H:%M")
    except ValueError:
        return iso_timestamp[:16]


def render_past_sessions() -> None:
    sessions = api_client.list_sessions(limit=10)
    if not sessions:
        st.caption(i18n.t("no_past_sessions"))
        return

    for session in sessions:
        label = (
            f"{session['lesson_title']} — "
            f"{session['grammar_score']}% — "
            f"{_format_date(session['ended_at'])}"
        )
        with st.expander(label):
            detail = api_client.get_session(session["id"])
            if not detail:
                continue
            st.write(f"{i18n.t('exchanges_label')} {detail['exchange_count']}")
            st.write(f"{i18n.t('mistakes_colon_label')} {detail['mistake_count']}")
            if detail.get("vocabulary"):
                st.write(f"{i18n.t('vocabulary_colon_label')} {', '.join(detail['vocabulary'])}")
            if detail.get("mistake_types"):
                st.write(i18n.t("mistake_types_label"))
                for mt in detail["mistake_types"]:
                    st.write(f"• {mt['mistake_type']} ({mt['count']})")
            if detail.get("recommendation"):
                st.info(detail["recommendation"])


def render_sidebar(cookie_manager) -> None:
    with st.sidebar:
        st.title(i18n.t("app_title"))
        i18n.render_language_switcher(cookie_manager, key="sidebar_lang")
        st.markdown(i18n.rtl_style('[data-testid="stSidebar"]'), unsafe_allow_html=True)

        mode = st.session_state.get("mode")
        difficulty = st.session_state.get("difficulty")
        if mode and difficulty:
            st.caption(
                i18n.t(
                    "mode_difficulty_caption",
                    mode=i18n.mode_label(mode),
                    difficulty=i18n.difficulty_label(difficulty),
                )
            )

        if mode == "lesson":
            summaries = api_client.list_lessons()
            if not summaries:
                st.warning(i18n.t("no_lessons_available"))
                return

            lesson_titles = {summary["title"]: summary["id"] for summary in summaries}

            selected_title = st.selectbox(
                i18n.t("choose_lesson_label"),
                options=list(lesson_titles.keys()),
                index=0,
            )

            if selected_title:
                lesson = api_client.get_lesson(lesson_titles[selected_title])
                if lesson:
                    st.session_state.lesson = lesson

        st.divider()
        st.subheader(i18n.t("progress_header"))

        score = st.session_state.score.get("grammar", 0)
        st.metric(i18n.t("grammar_score_label"), f"{score}%")

        usage = api_client.get_usage_today()
        if usage:
            st.caption(
                i18n.t(
                    "messages_today_caption",
                    used=usage["messages_used"],
                    limit=usage["messages_limit"],
                )
            )

        if st.session_state.mistakes:
            st.caption(i18n.t("common_mistakes_label"))
            for mistake in st.session_state.mistakes[-5:]:
                mistake_type = (
                    mistake.get("mistake_type")
                    if isinstance(mistake, dict)
                    else mistake.mistake_type
                )
                st.write(f"• {mistake_type or i18n.t('unknown_mistake')}")

        if st.session_state.vocabulary:
            st.caption(i18n.t("vocabulary_label"))
            for word in st.session_state.vocabulary[-8:]:
                st.write(f"• {word}")

        st.divider()

        if st.session_state.conversation_started and not st.session_state.session_ended:
            if st.button(i18n.t("end_session_button"), use_container_width=True):
                st.session_state.session_ended = True
                st.rerun()

        st.subheader(i18n.t("past_sessions_header"))
        render_past_sessions()
