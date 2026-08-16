"""Mode + difficulty picker — shown after login until both are chosen."""

import streamlit as st

MODE_LABELS = {"lesson": "درس", "free_talk": "محادثة حرة"}
DIFFICULTY_LABELS = {
    "beginner": "مبتدئ",
    "intermediate": "متوسط",
    "advanced": "متقدم",
}

RTL_MODE_PICKER_CSS = (
    '<style>.st-key-mode-picker-rtl { direction: rtl; text-align: right; }</style>'
)


def render_mode_picker() -> None:
    with st.container(key="mode-picker-rtl"):
        st.markdown(RTL_MODE_PICKER_CSS, unsafe_allow_html=True)
        st.header("كيف تريد أن تتدرّب؟")

        mode = st.radio(
            "الوضع",
            options=list(MODE_LABELS.keys()),
            format_func=lambda key: MODE_LABELS[key],
        )

        difficulty = st.radio(
            "المستوى",
            options=list(DIFFICULTY_LABELS.keys()),
            format_func=lambda key: DIFFICULTY_LABELS[key],
        )

        continue_clicked = st.button("متابعة", type="primary")

    if continue_clicked:
        st.session_state.mode = mode
        st.session_state.difficulty = difficulty
        if mode == "free_talk":
            st.session_state.lesson = None
            st.session_state.conversation_started = True
        st.rerun()
