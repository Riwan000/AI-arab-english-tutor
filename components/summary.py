"""End-of-session performance summary."""

import streamlit as st

import api_client


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
        st.session_state.lesson.get("title", "this lesson")
        if st.session_state.lesson
        else "this lesson"
    )
    recommendation = None
    if grammar < 70:
        recommendation = f"Practice {lesson_title} again tomorrow."
    elif grammar >= 90:
        recommendation = "Excellent work! Try a harder lesson next."
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
    if not lesson or not messages:
        return None

    result = api_client.save_session(
        lesson_id=lesson["id"],
        messages=messages,
        mistakes=st.session_state.mistakes,
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
    st.header("Session Summary")

    saved_id = persist_session()
    summary = _load_summary()

    if saved_id:
        st.caption(f"Session saved (#{saved_id})")
    elif st.session_state.messages and not st.session_state.get("session_persisted"):
        st.caption("Session could not be saved to the server.")

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
