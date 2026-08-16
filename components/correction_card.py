"""Grammar correction card with English and Arabic explanations."""

import html
import json

import streamlit as st
import streamlit.components.v1 as components

import i18n
from models.feedback import GrammarFeedback

ARABIC_EXPLANATION_CSS = (
    "<style>.rtl-arabic-explanation { direction: rtl; text-align: right; "
    "font-size: 1.05rem; font-weight: 600; margin: 0.4rem 0; }</style>"
)


def _js_string_literal(text: str) -> str:
    """Encode `text` as a JS string literal that is safe inside a <script> block.

    `json.dumps` alone is not enough: it escapes quotes and backslashes for the
    JS-string context, but the HTML tokenizer runs *first* and keeps scanning
    raw script text for "</script>" (which would end the element early and turn
    the rest of the interpolation into live markup) and for "<!--<script"
    (which enters the script-data-double-escaped state and swallows our real
    closing tag). Re-encoding every "<" as the \\u003c escape defeats both while
    parsing back to a byte-identical string. json.dumps' default
    ensure_ascii=True already escapes U+2028/U+2029, the other JS-literal
    line-terminator hazard.
    """
    return json.dumps(text).replace("<", "\\u003c")


def _speak_arabic(text: str) -> None:
    """Read `text` aloud via the browser's built-in speech synthesis.

    Deepgram's Aura voices don't cover Arabic (services/voice.py), so this
    plays client-side instead of round-tripping to /voice/speak, which would
    just 400 for a non-English language.

    `text` is LLM output steered by learner chat input, so it is untrusted and
    must be encoded for the <script> context, not the HTML-text context.
    """
    components.html(
        f"""<script>
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance({_js_string_literal(text)});
        utterance.lang = "ar-SA";
        window.speechSynthesis.speak(utterance);
        </script>""",
        height=0,
    )


def render_correction_card(feedback: list[GrammarFeedback] | list[dict], key_prefix: str) -> None:
    for idx, item in enumerate(feedback):
        data = item if isinstance(item, dict) else item.model_dump()

        with st.container(border=True):
            st.markdown(f"**{i18n.t('correction_title')}**")
            st.markdown(f"{i18n.t('your_sentence_label')} {data.get('wrong_text', '')}")
            st.markdown(f"{i18n.t('better_sentence_label')} {data.get('correct_text', '')}")

            if arabic_explanation := data.get("arabic_explanation"):
                st.markdown(ARABIC_EXPLANATION_CSS, unsafe_allow_html=True)
                st.markdown(
                    f'<div class="rtl-arabic-explanation">'
                    f"{html.escape(arabic_explanation)}</div>",
                    unsafe_allow_html=True,
                )
                if st.button(i18n.t("listen_button"), key=f"{key_prefix}_listen_{idx}"):
                    _speak_arabic(arabic_explanation)

            if english_explanation := data.get("english_explanation"):
                st.caption(english_explanation)

            if tip := data.get("tip"):
                st.caption(f"{i18n.t('tip_label')} {tip}")
