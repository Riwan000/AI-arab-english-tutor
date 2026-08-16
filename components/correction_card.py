"""Grammar correction card with English and Arabic explanations."""

import html

import streamlit as st

from models.feedback import GrammarFeedback

ARABIC_EXPLANATION_CSS = (
    "<style>.rtl-arabic-explanation { direction: rtl; text-align: right; "
    "font-size: 1.05rem; font-weight: 600; margin: 0.4rem 0; }</style>"
)


def render_correction_card(feedback: list[GrammarFeedback] | list[dict]) -> None:
    for item in feedback:
        data = item if isinstance(item, dict) else item.model_dump()

        with st.container(border=True):
            st.markdown("**Almost! Just one small change.**")
            st.markdown(f"❌ **Your sentence:** {data.get('wrong_text', '')}")
            st.markdown(f"✅ **Better sentence:** {data.get('correct_text', '')}")

            if arabic_explanation := data.get("arabic_explanation"):
                st.markdown(ARABIC_EXPLANATION_CSS, unsafe_allow_html=True)
                st.markdown(
                    f'<div class="rtl-arabic-explanation">'
                    f"{html.escape(arabic_explanation)}</div>",
                    unsafe_allow_html=True,
                )

            if english_explanation := data.get("english_explanation"):
                st.caption(english_explanation)

            if tip := data.get("tip"):
                st.caption(f"💡 Tip: {tip}")
