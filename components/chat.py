"""Main chat interface for guided AI conversation."""

from datetime import datetime, timezone

import streamlit as st

from components.correction_card import render_correction_card
from prompts.prompt_builder import build_messages
from services.grammar import extract_feedback
from services.openrouter import chat_completion


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
    messages = build_messages(lesson, st.session_state.messages, start=True)
    response = chat_completion(messages)
    assistant_message = {
        "role": "assistant",
        "content": response,
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

    messages = build_messages(lesson, st.session_state.messages)
    response = chat_completion(messages)
    feedback = extract_feedback(response)

    if feedback:
        for item in feedback:
            entry = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            entry["message_index"] = user_message_index
            st.session_state.mistakes.append(entry)

    assistant_message = {
        "role": "assistant",
        "content": response,
        "feedback": feedback,
        "has_correction": bool(feedback),
        **_message_metadata(lesson),
    }
    st.session_state.messages.append(assistant_message)
    st.rerun()
