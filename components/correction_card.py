"""Grammar correction card with English and Arabic explanations."""

import streamlit as st

from models.feedback import GrammarFeedback


def render_correction_card(feedback: list[GrammarFeedback] | list[dict]) -> None:
    for item in feedback:
        data = item if isinstance(item, dict) else item.model_dump()

        with st.container(border=True):
            st.markdown("**Almost! Just one small change.**")
            st.markdown(f"❌ **Your sentence:** {data.get('wrong_text', '')}")
            st.markdown(f"✅ **Better sentence:** {data.get('correct_text', '')}")
            st.markdown(f"**Grammar rule:** {data.get('english_explanation', '')}")
            st.markdown(f"**بالعربية:** {data.get('arabic_explanation', '')}")

            if tip := data.get("tip"):
                st.caption(f"💡 Tip: {tip}")
