"""Lesson viewer: displays grammar explanation before practice starts."""

import streamlit as st

import api_client


def render_lesson_view() -> None:
    lesson_meta = st.session_state.get("lesson")
    if not lesson_meta or not lesson_meta.get("id"):
        st.warning("الرجاء اختيار درس من الشريط الجانبي.")
        return

    lesson = api_client.get_lesson(lesson_meta["id"])
    if not lesson:
        st.warning("تعذر تحميل تفاصيل الدرس.")
        return

    st.session_state.lesson = lesson

    st.header(lesson["title"])
    st.write(lesson["description"])

    st.subheader("أمثلة")
    for example in lesson.get("examples", []):
        st.code(example, language=None)

    if lesson.get("negative_form"):
        st.subheader("النفي")
        for item in lesson["negative_form"]:
            st.code(item, language=None)

    if lesson.get("question_form"):
        st.subheader("السؤال")
        for item in lesson["question_form"]:
            st.code(item, language=None)

    if lesson.get("tips"):
        st.subheader("نصائح")
        for tip in lesson["tips"]:
            st.info(tip)

    if st.button("ابدأ التدريب", type="primary"):
        st.session_state.conversation_started = True
        st.rerun()
