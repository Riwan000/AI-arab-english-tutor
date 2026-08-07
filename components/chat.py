"""Main chat interface for guided AI conversation."""

from datetime import datetime, timezone

import streamlit as st

from components.correction_card import render_correction_card
from services.conversation import send_message, start_conversation
from services.errors import AppError


def render_chat() -> None:
    lesson = st.session_state.get("lesson")
    if not lesson:
        st.warning("Please select a lesson from the sidebar.")
        return

    st.header(f"Practice: {lesson['title']}")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("feedback"):
                render_correction_card(message["feedback"])

    if not st.session_state.messages:
        _start_conversation(lesson)

    if prompt := st.chat_input("Type your answer in English..."):
        _handle_user_message(prompt, lesson)


def _message_metadata(lesson: dict) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lesson_id": lesson["id"],
    }


def _start_conversation(lesson: dict) -> None:
    try:
        result = start_conversation(lesson["id"])
    except AppError as exc:
        st.error(exc.detail)
        return

    assistant_message = {
        "role": "assistant",
        "content": result.reply,
        "has_correction": False,
        **_message_metadata(lesson),
    }
    st.session_state.messages.append(assistant_message)
    st.rerun()


def _handle_user_message(user_text: str, lesson: dict) -> None:
    st.session_state.messages.append({
        "role": "user",
        "content": user_text,
        **_message_metadata(lesson),
    })
    user_message_index = len(st.session_state.messages) - 1

    try:
        result = send_message(
            lesson_id=lesson["id"],
            messages=st.session_state.messages[:-1],
            user_text=user_text,
        )
    except AppError as exc:
        st.error(exc.detail)
        st.session_state.messages.pop()
        return

    feedback = [item.model_dump() for item in result.corrections]
    if feedback:
        for entry in feedback:
            entry["message_index"] = user_message_index
            st.session_state.mistakes.append(entry)

    assistant_message = {
        "role": "assistant",
        "content": result.reply,
        "feedback": feedback,
        "has_correction": bool(feedback),
        **_message_metadata(lesson),
    }
    st.session_state.messages.append(assistant_message)
    st.rerun()
