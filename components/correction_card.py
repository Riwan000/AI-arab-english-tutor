"""Grammar correction display with English and Arabic explanations."""

import streamlit as st

import i18n
from models.feedback import GrammarFeedback


def render_correction_card(
    feedback: list[GrammarFeedback] | list[dict],
    key_prefix: str,
) -> None:

    for idx, item in enumerate(feedback):
        data = item if isinstance(item, dict) else item.model_dump()

        st.markdown(
            f"""
            <div style="background-color: #f2fbf5; border: 1px solid #c3eccf; border-radius: 14px; padding: 16px 18px; margin: 12px 0;">
                <div style="font-weight: 700; font-size: 0.98rem; color: #166534; margin-bottom: 10px;">
                    {i18n.t('correction_title')}
                </div>
            """,
            unsafe_allow_html=True,
        )

        wrong_text = data.get("wrong_text", "")
        if wrong_text:
            st.markdown(
                f"{i18n.t('your_sentence_label')} {wrong_text}"
            )

        correct_text = data.get("correct_text", "")
        if correct_text:
            st.markdown(
                f"{i18n.t('better_sentence_label')} {correct_text}"
            )

        arabic_explanation = data.get("arabic_explanation")
        if arabic_explanation:
            st.markdown(
                f"""
                <div dir="rtl" style="text-align: right; font-size: 1.05rem; font-weight: 600; color: #14532d; margin: 12px 0 8px 0; line-height: 1.6;">
                    {arabic_explanation}
                </div>
                """,
                unsafe_allow_html=True,
            )

        english_explanation = data.get("english_explanation")
        if english_explanation:
            st.caption(english_explanation)

        tip = data.get("tip")
        if tip:
            st.caption(
                f"{i18n.t('tip_label')} {tip}"
            )

        st.markdown("</div>", unsafe_allow_html=True)