"""Lesson viewer: displays grammar explanation before practice starts."""

import streamlit as st

import api_client
import i18n


def render_lesson_view() -> None:
    lesson_meta = st.session_state.get("lesson")
    if not lesson_meta or not lesson_meta.get("id"):
        st.warning(i18n.t("choose_lesson_warning"))
        return

    lesson = api_client.get_lesson(lesson_meta["id"])
    if not lesson:
        st.warning(i18n.t("lesson_load_error"))
        return

    st.session_state.lesson = lesson

    st.header(lesson["title"])
    st.write(lesson["description"])

    st.subheader(i18n.t("examples_header"))
    for example in lesson.get("examples", []):
        st.code(example, language=None)

    if lesson.get("negative_form"):
        st.subheader(i18n.t("negative_form_header"))
        for item in lesson["negative_form"]:
            st.code(item, language=None)

    if lesson.get("question_form"):
        st.subheader(i18n.t("question_form_header"))
        for item in lesson["question_form"]:
            st.code(item, language=None)

    if lesson.get("tips"):
        st.subheader(i18n.t("tips_header"))
        for tip in lesson["tips"]:
            st.info(tip)

    if st.button(i18n.t("start_training_button"), type="primary"):
        st.session_state.conversation_started = True
        st.rerun()
