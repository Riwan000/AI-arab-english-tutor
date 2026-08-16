"""Sidebar: lesson selector, score, mistakes, vocabulary, end session."""

from datetime import datetime

import streamlit as st

import api_client
from components.mode_picker import DIFFICULTY_LABELS, MODE_LABELS


def _format_date(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%b %d, %H:%M")
    except ValueError:
        return iso_timestamp[:16]


RTL_SIDEBAR_CSS = '<style>[data-testid="stSidebar"] { direction: rtl; text-align: right; }</style>'


def render_past_sessions() -> None:
    sessions = api_client.list_sessions(limit=10)
    if not sessions:
        st.caption("لا توجد جلسات سابقة بعد.")
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
            st.write(f"**التبادلات:** {detail['exchange_count']}")
            st.write(f"**الأخطاء:** {detail['mistake_count']}")
            if detail.get("vocabulary"):
                st.write(f"**المفردات:** {', '.join(detail['vocabulary'])}")
            if detail.get("mistake_types"):
                st.write("**أنواع الأخطاء:**")
                for mt in detail["mistake_types"]:
                    st.write(f"• {mt['mistake_type']} ({mt['count']})")
            if detail.get("recommendation"):
                st.info(detail["recommendation"])


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(RTL_SIDEBAR_CSS, unsafe_allow_html=True)
        st.title("📚 معلم اللغة الإنجليزية")

        mode = st.session_state.get("mode")
        difficulty = st.session_state.get("difficulty")
        if mode and difficulty:
            st.caption(
                f"الوضع: {MODE_LABELS.get(mode, mode)} · "
                f"المستوى: {DIFFICULTY_LABELS.get(difficulty, difficulty)}"
            )

        if mode == "lesson":
            summaries = api_client.list_lessons()
            if not summaries:
                st.warning("لا توجد دروس متاحة. تحقق من الاتصال بالخادم.")
                return

            lesson_titles = {summary["title"]: summary["id"] for summary in summaries}

            selected_title = st.selectbox(
                "اختر درسًا",
                options=list(lesson_titles.keys()),
                index=0,
            )

            if selected_title:
                lesson = api_client.get_lesson(lesson_titles[selected_title])
                if lesson:
                    st.session_state.lesson = lesson

        st.divider()
        st.subheader("التقدم")

        score = st.session_state.score.get("grammar", 0)
        st.metric("درجة القواعد", f"{score}%")

        usage = api_client.get_usage_today()
        if usage:
            st.caption(f"الرسائل اليوم: {usage['messages_used']}/{usage['messages_limit']}")

        if st.session_state.mistakes:
            st.caption("الأخطاء الشائعة")
            for mistake in st.session_state.mistakes[-5:]:
                mistake_type = (
                    mistake.get("mistake_type")
                    if isinstance(mistake, dict)
                    else mistake.mistake_type
                )
                st.write(f"• {mistake_type or 'غير معروف'}")

        if st.session_state.vocabulary:
            st.caption("المفردات")
            for word in st.session_state.vocabulary[-8:]:
                st.write(f"• {word}")

        st.divider()

        if st.session_state.conversation_started and not st.session_state.session_ended:
            if st.button("إنهاء الجلسة", use_container_width=True):
                st.session_state.session_ended = True
                st.rerun()

        st.subheader("الجلسات السابقة")
        render_past_sessions()
