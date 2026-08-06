"""Lesson viewer: displays grammar explanation before practice starts."""

import streamlit as st


def render_lesson_view() -> None:
    lesson = st.session_state.get("lesson")

    if not lesson:
        st.warning("Please select a lesson from the sidebar.")
        return

    st.header(lesson["title"])
    st.write(lesson["description"])

    st.subheader("Examples")
    for example in lesson.get("examples", []):
        st.code(example, language=None)

    if lesson.get("negative_form"):
        st.subheader("Negative")
        for item in lesson["negative_form"]:
            st.code(item, language=None)

    if lesson.get("question_form"):
        st.subheader("Question")
        for item in lesson["question_form"]:
            st.code(item, language=None)

    if lesson.get("tips"):
        st.subheader("Tips")
        for tip in lesson["tips"]:
            st.info(tip)

    if st.button("Start Practice", type="primary"):
        st.session_state.conversation_started = True
        st.rerun()
