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
