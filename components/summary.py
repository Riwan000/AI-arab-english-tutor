"""End-of-session performance summary."""

import streamlit as st

import api_client
import i18n


def _summary_from_save(result: dict) -> dict:
    return {
        "grammar": result.get("grammar_score", 0),
        "exchanges": result.get("exchange_count", 0),
        "mistake_count": result.get("mistake_count", 0),
        "mistake_types": result.get("mistake_types", []),
        "vocabulary": result.get("vocabulary", []),
        "recommendation": result.get("recommendation"),
    }


def _summary_from_detail(detail: dict) -> dict:
    mistake_types = detail.get("mistake_types", [])
    if mistake_types and isinstance(mistake_types[0], dict):
        types = [item["mistake_type"] for item in mistake_types]
    else:
        types = mistake_types
    return {
        "grammar": detail.get("grammar_score", 0),
        "exchanges": detail.get("exchange_count", 0),
        "mistake_count": detail.get("mistake_count", 0),
        "mistake_types": types,
        "vocabulary": detail.get("vocabulary", []),
        "recommendation": detail.get("recommendation"),
    }


def _local_preview_summary() -> dict:
    """Fallback summary when the API is unavailable."""
    mistakes = st.session_state.mistakes
    messages = st.session_state.messages
    user_messages = [m for m in messages if m["role"] == "user"]
    exchanges = len(user_messages)
    mistake_count = len(mistakes)
    mistake_types = list(
        dict.fromkeys(
            m.get("mistake_type", "Unknown")
            for m in mistakes
            if isinstance(m, dict) and m.get("mistake_type")
        )
    )
    grammar = max(0, 100 - mistake_count * 10) if exchanges else 0
    lesson_title = (
        st.session_state.lesson.get("title", i18n.t("this_lesson_fallback"))
        if st.session_state.lesson
        else i18n.t("this_lesson_fallback")
    )
    recommendation = None
    if grammar < 70:
        recommendation = i18n.t("recommendation_default", lesson=lesson_title)
    elif grammar >= 90:
        recommendation = i18n.t("excellent_recommendation")
    return {
        "grammar": grammar,
        "exchanges": exchanges,
        "mistake_count": mistake_count,
        "mistake_types": mistake_types,
        "vocabulary": st.session_state.get("vocabulary", []),
        "recommendation": recommendation,
    }


def persist_session() -> int | None:
    """Save the current session via API if it has messages and is not yet persisted."""
    if st.session_state.get("session_persisted"):
        return st.session_state.get("saved_conversation_id")

    lesson = st.session_state.get("lesson")
    messages = st.session_state.get("messages", [])
    if not messages:
        return None

    result = api_client.save_session(
        lesson_id=lesson["id"] if lesson else None,
        messages=messages,
        mistakes=st.session_state.mistakes,
        mode=st.session_state.get("mode", "lesson"),
    )

    if result and result.get("id"):
        st.session_state.session_persisted = True
        st.session_state.saved_conversation_id = result["id"]
        st.session_state.score = _summary_from_save(result)
        if result.get("vocabulary"):
            st.session_state.vocabulary = result["vocabulary"]
        return result["id"]

    return None


def _load_summary() -> dict:
    if st.session_state.get("score"):
        return st.session_state.score

    saved_id = st.session_state.get("saved_conversation_id")
    if saved_id:
        detail = api_client.get_session(saved_id)
        if detail:
            summary = _summary_from_detail(detail)
            st.session_state.score = summary
            return summary

    summary = _local_preview_summary()
    st.session_state.score = summary
    return summary


def render_summary() -> None:
    with st.container(key="summary-rtl"):
        st.markdown(
            i18n.rtl_style(".st-key-summary-rtl"),
            unsafe_allow_html=True,
        )
        st.header(i18n.t("session_summary_header"))

        saved_id = persist_session()
        summary = _load_summary()

        if saved_id:
            st.caption(i18n.t("session_saved_caption", id=saved_id))
        elif st.session_state.messages and not st.session_state.get("session_persisted"):
            st.caption(i18n.t("session_save_failed_caption"))

        col1, col2, col3 = st.columns(3)
        col1.metric(i18n.t("grammar_score_label"), f"{summary['grammar']}%")
        col2.metric(i18n.t("exchanges_metric_label"), summary["exchanges"])
        col3.metric(i18n.t("mistakes_metric_label"), summary["mistake_count"])

        st.subheader(i18n.t("vocabulary_label"))
        if summary["vocabulary"]:
            st.write(", ".join(summary["vocabulary"]))
        else:
            st.write(i18n.t("no_vocabulary_tracked"))

        st.subheader(i18n.t("common_mistakes_label"))
        if summary["mistake_types"]:
            for mistake_type in summary["mistake_types"]:
                st.write(f"• {mistake_type}")
        else:
            st.write(i18n.t("no_mistakes"))

        st.subheader(i18n.t("recommendation_header"))
        if st.session_state.lesson:
            lesson_title = st.session_state.lesson["title"]
        elif st.session_state.get("mode") == "free_talk":
            lesson_title = i18n.mode_label("free_talk")
        else:
            lesson_title = i18n.t("this_lesson_fallback")
        st.info(
            summary.get("recommendation")
            or i18n.t("recommendation_default", lesson=lesson_title)
        )

        if st.button(i18n.t("new_session_button")):
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
    st.session_state.lesson = None
    st.session_state.mode = None
    st.session_state.difficulty = None
    st.session_state._last_played_audio_index = -1
