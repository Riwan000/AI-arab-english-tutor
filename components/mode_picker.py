"""Mode + difficulty picker — shown after login until both are chosen."""

import streamlit as st

import i18n


def render_mode_picker() -> None:
    with st.container(key="mode-picker-rtl"):
        st.markdown(i18n.rtl_style(".st-key-mode-picker-rtl"), unsafe_allow_html=True)
        st.header(i18n.t("mode_picker_header"))

        mode = st.radio(
            i18n.t("mode_field_label"),
            options=list(i18n.MODE_LABELS[i18n.DEFAULT_LANGUAGE].keys()),
            format_func=i18n.mode_label,
        )

        difficulty = st.radio(
            i18n.t("difficulty_field_label"),
            options=list(i18n.DIFFICULTY_LABELS[i18n.DEFAULT_LANGUAGE].keys()),
            format_func=i18n.difficulty_label,
        )

        continue_clicked = st.button(i18n.t("continue_button"), type="primary")

    if continue_clicked:
        st.session_state.mode = mode
        st.session_state.difficulty = difficulty
        if mode == "free_talk":
            st.session_state.lesson = None
            st.session_state.conversation_started = True
        st.rerun()
