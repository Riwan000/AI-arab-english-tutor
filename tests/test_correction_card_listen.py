"""Correction card listen button (issue #158): Arabic explanations are read
aloud via browser-native speech synthesis rather than /voice/speak, since
Deepgram's Aura voices don't cover Arabic (api/routes/voice.py).
"""

import json
from unittest.mock import MagicMock, patch

import components.correction_card as card_module


def _feedback(**overrides):
    base = {
        "wrong_text": "I go yesterday",
        "correct_text": "I went yesterday",
        "arabic_explanation": "استخدم الماضي هنا",
        "english_explanation": "Use past tense here",
        "tip": "Remember -ed endings",
    }
    return {**base, **overrides}


def test_listen_button_speaks_arabic_explanation_when_clicked(monkeypatch):
    st = MagicMock()
    st.button.return_value = True
    speak_arabic = MagicMock()
    monkeypatch.setattr(card_module, "_speak_arabic", speak_arabic)

    with patch.object(card_module, "st", st):
        card_module.render_correction_card([_feedback()], key_prefix="msg0")

    speak_arabic.assert_called_once_with("استخدم الماضي هنا")


def test_listen_button_not_shown_without_arabic_explanation(monkeypatch):
    st = MagicMock()
    speak_arabic = MagicMock()
    monkeypatch.setattr(card_module, "_speak_arabic", speak_arabic)

    with patch.object(card_module, "st", st):
        card_module.render_correction_card([_feedback(arabic_explanation="")], key_prefix="msg0")

    st.button.assert_not_called()
    speak_arabic.assert_not_called()


def test_listen_button_keys_are_unique_across_multiple_corrections_in_one_card():
    st = MagicMock()
    st.button.return_value = False

    with patch.object(card_module, "st", st):
        card_module.render_correction_card(
            [_feedback(wrong_text="a"), _feedback(wrong_text="b")], key_prefix="msg0"
        )

    keys = [call.kwargs["key"] for call in st.button.call_args_list]
    assert keys == ["msg0_listen_0", "msg0_listen_1"]


def test_listen_button_keys_are_unique_across_different_messages():
    """Two chat messages each with corrections must not collide on the same
    widget key (each render_correction_card call restarts idx from 0)."""
    st = MagicMock()
    st.button.return_value = False

    with patch.object(card_module, "st", st):
        card_module.render_correction_card([_feedback()], key_prefix="msg0")
        card_module.render_correction_card([_feedback()], key_prefix="msg3")

    keys = [call.kwargs["key"] for call in st.button.call_args_list]
    assert keys == ["msg0_listen_0", "msg3_listen_0"]
    assert len(keys) == len(set(keys))


def _rendered_markup(text: str) -> str:
    html_out = {}

    def fake_html(markup, **kwargs):
        html_out["markup"] = markup

    with patch.object(card_module.components, "html", fake_html):
        card_module._speak_arabic(text)

    return html_out["markup"]


def _embedded_js_literal(markup: str) -> str:
    """Pull the SpeechSynthesisUtterance argument back out of the markup.

    json.dumps never emits a raw newline, so the literal always sits on one
    line and ends the statement with `);`.
    """
    line = markup.split("SpeechSynthesisUtterance(", 1)[1].split("\n", 1)[0]
    assert line.endswith(");"), line
    return line[: -len(");")]


def test_speak_arabic_embeds_the_text_as_a_json_escaped_js_string():
    markup = _rendered_markup('نص فيه "علامات اقتباس"')

    assert '\\"' in markup or "\\u0022" in markup
    assert "speechSynthesis.speak" in markup
    assert 'utterance.lang = "ar-SA"' in markup


def test_speak_arabic_does_not_let_the_text_close_the_script_tag_early():
    """arabic_explanation is LLM output steered by learner chat input, so a
    literal '</script>' inside it must not terminate the <script> block and
    turn the remainder of the interpolation into live markup."""
    markup = _rendered_markup("</script><img src=x onerror=alert(1)>")

    assert "</script><img" not in markup
    assert "<img" not in markup
    assert "onerror" in markup  # still present, but inert inside the JS string
    # Exactly one </script> remains: the one this function writes itself.
    assert markup.count("</script>") == 1
    assert markup.rstrip().endswith("</script>")


def test_speak_arabic_neutralises_the_script_data_double_escape_sequence():
    """'<!--<script' puts the tokenizer in the script-data-double-escaped
    state, where our own closing tag would no longer end the element."""
    markup = _rendered_markup("<!--<script>payload")

    assert "<!--" not in markup
    assert "<script>payload" not in markup
    assert markup.count("</script>") == 1
    assert markup.count("<script>") == 1


def test_speak_arabic_escaping_round_trips_to_the_original_text():
    """The escaping must be transparent to speechSynthesis: the JS literal has
    to parse back to the exact original string, or the wrong text is spoken."""
    cases = (
        "استخدم الماضي هنا",
        "</script>",
        "a\\<b",
        'quote " and \u2028 line \u2029 separator',
        "plain ascii",
    )
    for text in cases:
        literal = _embedded_js_literal(_rendered_markup(text))
        assert json.loads(literal) == text
