"""Tests for services/grammar.py's LLM turn parsing."""

import json

from services import grammar


def test_parse_response_reads_reply_and_corrections_from_json_object():
    raw = json.dumps({
        "reply": "Almost! Try again.\n\nDo you like tea?",
        "corrections": [{
            "mistake_type": "Word Choice",
            "wrong_text": "tea without some sugar",
            "correct_text": "tea without sugar",
            "english_explanation": "Drop 'some'.",
            "arabic_explanation": "احذف 'some'.",
            "tip": "Try again.",
        }],
    })

    reply, corrections = grammar.parse_response(raw)

    assert reply == "Almost! Try again.\n\nDo you like tea?"
    assert len(corrections) == 1
    assert corrections[0].mistake_type == "Word Choice"
    assert corrections[0].correct_text == "tea without sugar"


def test_parse_response_returns_empty_corrections_when_no_mistake_made():
    raw = json.dumps({"reply": "Great job! Tell me more.", "corrections": []})

    reply, corrections = grammar.parse_response(raw)

    assert reply == "Great job! Tell me more."
    assert corrections == []


def test_parse_response_falls_back_to_fenced_block_for_legacy_shaped_replies():
    raw = (
        "Good try! Let's fix one small thing.\n"
        "```json\n"
        '{"corrections": [{'
        '"mistake_type": "tense", "wrong_text": "I go", "correct_text": "I went", '
        '"english_explanation": "Use past tense.", "arabic_explanation": "استخدم الماضي.", '
        '"tip": "Try again."'
        "}]}\n"
        "```"
    )

    reply, corrections = grammar.parse_response(raw)

    assert "```json" not in reply
    assert reply == "Good try! Let's fix one small thing."
    assert len(corrections) == 1
    assert corrections[0].wrong_text == "I go"


def test_parse_response_treats_plain_text_as_the_whole_reply():
    reply, corrections = grammar.parse_response("Hello! How are you today?")

    assert reply == "Hello! How are you today?"
    assert corrections == []


def test_parse_response_shows_a_generic_fallback_when_reply_key_is_missing():
    raw = json.dumps({"corrections": []})

    reply, corrections = grammar.parse_response(raw)

    assert reply == grammar._GENERIC_FALLBACK_REPLY
    assert "{" not in reply
    assert corrections == []


def test_parse_response_shows_a_generic_fallback_when_reply_is_not_a_string():
    raw = json.dumps({"reply": {"nested": "object"}, "corrections": []})

    reply, corrections = grammar.parse_response(raw)

    assert reply == grammar._GENERIC_FALLBACK_REPLY
    assert "{" not in reply
    assert corrections == []


def test_parse_response_uses_an_alternate_key_when_reply_key_is_absent():
    raw = json.dumps({"message": "Hello! How can I help?", "corrections": []})

    reply, corrections = grammar.parse_response(raw)

    assert reply == "Hello! How can I help?"
    assert corrections == []


def test_parse_response_ignores_malformed_correction_items():
    raw = json.dumps({
        "reply": "Almost!",
        "corrections": [{"mistake_type": "Verb Form"}],
    })

    reply, corrections = grammar.parse_response(raw)

    assert reply == "Almost!"
    assert corrections == []


def test_parse_response_survives_non_list_corrections_field():
    raw = json.dumps({"reply": "Great job!", "corrections": None})

    reply, corrections = grammar.parse_response(raw)

    assert reply == "Great job!"
    assert corrections == []


# --- extract_session_ending ----------------------------------------------------


def test_extract_session_ending_reads_true_from_json():
    raw = json.dumps({"reply": "Bye!", "corrections": [], "session_ending": True})

    assert grammar.extract_session_ending(raw) is True


def test_extract_session_ending_reads_false_from_json():
    raw = json.dumps({"reply": "Tell me more.", "corrections": [], "session_ending": False})

    assert grammar.extract_session_ending(raw) is False


def test_extract_session_ending_defaults_false_when_field_missing():
    raw = json.dumps({"reply": "Tell me more.", "corrections": []})

    assert grammar.extract_session_ending(raw) is False


def test_extract_session_ending_defaults_false_for_non_json_response():
    assert grammar.extract_session_ending("Hello! How are you?") is False


def test_extract_session_ending_defaults_false_for_non_dict_json():
    assert grammar.extract_session_ending(json.dumps(["reply", "corrections"])) is False


def test_extract_session_ending_coerces_truthy_non_bool_value():
    raw = json.dumps({"reply": "Bye!", "corrections": [], "session_ending": "true"})

    assert grammar.extract_session_ending(raw) is True


def test_extract_session_ending_reads_true_from_fenced_block_with_corrections():
    raw = (
        "Bye! It was great practicing with you.\n"
        "```json\n"
        '{"corrections": [{'
        '"mistake_type": "tense", "wrong_text": "I go", "correct_text": "I went", '
        '"english_explanation": "Use past tense.", "arabic_explanation": "استخدم الماضي.", '
        '"tip": "Try again."'
        '}], "session_ending": true}\n'
        "```"
    )

    assert grammar.extract_session_ending(raw) is True


def test_extract_session_ending_reads_true_from_fenced_block_without_corrections():
    raw = (
        "Goodbye! See you next time.\n"
        "```json\n"
        '{"session_ending": true}\n'
        "```"
    )

    assert grammar.extract_session_ending(raw) is True


def test_extract_session_ending_defaults_false_for_prose_with_no_fenced_block():
    raw = "Great job! Let's keep practicing. What did you do today?"

    assert grammar.extract_session_ending(raw) is False


def test_extract_session_ending_defaults_false_for_malformed_json_in_fence():
    raw = (
        "Bye!\n"
        "```json\n"
        '{"session_ending": true, "corrections": [}\n'
        "```"
    )

    assert grammar.extract_session_ending(raw) is False


# --- contains_farewell_keyword --------------------------------------------------


def test_contains_farewell_keyword_matches_common_english_farewells():
    assert grammar.contains_farewell_keyword("ok bye!") is True
    assert grammar.contains_farewell_keyword("Goodbye for now") is True
    assert grammar.contains_farewell_keyword("that's all for today, thanks") is True


def test_contains_farewell_keyword_matches_arabic_farewells():
    assert grammar.contains_farewell_keyword("مع السلامة") is True
    assert grammar.contains_farewell_keyword("خلصت شكرا") is True


def test_contains_farewell_keyword_is_case_insensitive():
    assert grammar.contains_farewell_keyword("BYE") is True


def test_contains_farewell_keyword_does_not_match_ordinary_text():
    assert grammar.contains_farewell_keyword("What is the weather like today?") is False
