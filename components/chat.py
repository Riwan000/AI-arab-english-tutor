"""Main chat interface for guided AI conversation."""

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


def _start_conversation(lesson: dict) -> None:
    messages = build_messages(lesson, st.session_state.messages, start=True)
    response = chat_completion(messages)
    assistant_message = {"role": "assistant", "content": response}
    st.session_state.messages.append(assistant_message)
    st.rerun()


def _handle_user_message(user_text: str, lesson: dict) -> None:
    st.session_state.messages.append({"role": "user", "content": user_text})

    messages = build_messages(lesson, st.session_state.messages)
    response = chat_completion(messages)
    feedback = extract_feedback(response)

    if feedback:
        st.session_state.mistakes.extend(feedback)

    assistant_message = {
        "role": "assistant",
        "content": response,
        "feedback": feedback,
    }
    st.session_state.messages.append(assistant_message)
    st.rerun()
