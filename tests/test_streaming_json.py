"""services/streaming_json.py: incremental "reply" field extraction from a
JSON object streaming in one chunk at a time from the LLM."""

import json
import threading

import pytest

from services.streaming_json import ReplyTextExtractor


def _feed_all(chunks) -> ReplyTextExtractor:
    extractor = ReplyTextExtractor()
    for chunk in chunks:
        extractor.feed(chunk)
    return extractor


def _feed_all_with_timeout(chunks, timeout=2.0) -> ReplyTextExtractor:
    """Like _feed_all, but off-thread with a hard timeout — a malformed
    \\uXXXX escape must never hang the decoder (regression coverage for a
    previously-real infinite loop), and calling feed() directly here would
    hang the whole test run instead of just failing this one test."""
    extractor = ReplyTextExtractor()
    done = threading.Event()

    def run():
        for chunk in chunks:
            extractor.feed(chunk)
        done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout)

    assert done.is_set(), f"feed() did not return within {timeout}s — decoder is stuck"
    return extractor


def test_decodes_a_plain_reply_in_one_chunk():
    extractor = _feed_all(['{"reply": "Hello world.", "corrections": []}'])

    assert extractor.decoded == "Hello world."
    assert extractor.done is True


def test_decodes_when_reply_is_not_the_first_key():
    extractor = _feed_all(['{"corrections": [], "reply": "Hi there."}'])

    assert extractor.decoded == "Hi there."


def test_stops_at_the_closing_quote_and_ignores_the_rest_of_the_object():
    extractor = _feed_all(
        ['{"reply": "Hi.", "corrections": [{"mistake_type": "reply-shaped text"}]}']
    )

    assert extractor.decoded == "Hi."
    assert extractor.done is True


def test_gives_up_when_reply_key_never_appears_within_the_preamble_cap():
    # The cap trips inside the first feed() (250 chars, no "reply" key found
    # yet); a later chunk that does contain the key must not resurrect it —
    # feed() short-circuits once _finished is set, exactly like a stream that
    # goes on to send corrections/session_ending but never a "reply" key.
    extractor = _feed_all(["{" + "x" * 250, '"reply": "too late"}'])

    assert extractor.decoded == ""
    assert extractor.done is True


def test_unrecognized_escape_stops_decoding_without_raising():
    extractor = _feed_all(['{"reply": "before \\x after"}'])

    assert extractor.decoded == "before "
    assert extractor.done is True


@pytest.mark.parametrize(
    "raw_reply",
    [
        "A simple sentence.",
        'He said "hello" to me.\nThen left.',
        "Tab\there and back\\slash.",
        "Almost! ✅ Correct.",
    ],
)
def test_matches_json_loads_when_fed_one_chunk_at_a_time(raw_reply):
    full = json.dumps({"reply": raw_reply, "corrections": []})
    expected = json.loads(full)["reply"]

    extractor = _feed_all(list(full))  # one character per feed() call

    assert extractor.decoded == expected


def test_matches_json_loads_when_fed_in_arbitrary_size_chunks():
    raw_reply = 'Great job!\n\n✅ Correct: "I go" → "I went".\nKeep going.'
    full = json.dumps({"reply": raw_reply, "corrections": [], "session_ending": False})
    expected = json.loads(full)["reply"]

    chunks = [full[i : i + 3] for i in range(0, len(full), 3)]
    extractor = _feed_all(chunks)

    assert extractor.decoded == expected


def test_escape_sequence_split_across_a_chunk_boundary():
    # "\n" split so one feed() ends on the bare backslash.
    extractor = _feed_all(['{"reply": "Line1\\', 'nLine2"}'])

    assert extractor.decoded == "Line1\nLine2"


def test_unicode_escape_split_mid_sequence():
    # ✅ (a check mark) split after only two of its four hex digits.
    extractor = _feed_all(['{"reply": "\\u27', '05 done"}'])

    assert extractor.decoded == "✅ done"


def test_surrogate_pair_split_across_two_feed_calls():
    # A flag emoji is a UTF-16 surrogate pair when escaped as \uXXXX\uXXXX.
    raw_reply = "Great! \U0001f1f8\U0001f1e6 done"
    full = json.dumps({"reply": raw_reply})
    expected = json.loads(full)["reply"]

    # Split immediately after the high surrogate's escape, before the low
    # surrogate's escape has arrived at all.
    idx = full.index("\\u")
    split_at = idx + 6  # end of the first \uXXXX escape

    extractor = _feed_all([full[:split_at], full[split_at:]])

    assert extractor.decoded == expected


def test_done_before_reply_key_found_short_circuits_feed():
    extractor = ReplyTextExtractor()
    extractor.feed('{"corrections": [')  # no "reply" key seen yet

    assert extractor.decoded == ""
    assert extractor.done is False

    assert extractor.feed("") == ""


# --- malformed \uXXXX escapes must give up, not hang ----------------------
#
# _decode_unicode_escape sets _finished=True and returns 0 (not None) on
# each of these — the give-up path, not the "need more input" path. The
# decode loop must stop on _finished even though i never advanced past the
# escape that triggered it.


def test_bad_hex_in_unicode_escape_stops_decoding_without_hanging():
    extractor = _feed_all_with_timeout(['{"reply": "before \\uZZZZ after"}'])

    assert extractor.decoded == "before "
    assert extractor.done is True


def test_lone_high_surrogate_with_no_further_chunks_waits_without_hanging():
    # Only 2 trailing chars follow the escape (`"}`) — not enough for the
    # 12-char surrogate-pair lookahead to even attempt a verdict, so this
    # correctly falls into "need more input", not the malformed-pair give-up
    # path. feed() must still return promptly either way: real callers just
    # stop calling feed() once the LLM stream ends, so a trailing char lost
    # to "still waiting" state is a benign, bounded miss — not a hang.
    extractor = _feed_all_with_timeout(['{"reply": "before \\ud83c"}'])

    assert extractor.decoded == "before "
    assert extractor.done is False


def test_high_surrogate_not_followed_by_another_escape_stops_decoding_without_hanging():
    extractor = _feed_all_with_timeout(['{"reply": "before \\ud83cXX after"}'])

    assert extractor.decoded == "before "
    assert extractor.done is True


def test_high_surrogate_followed_by_invalid_low_surrogate_stops_decoding_without_hanging():
    # A ("A") is valid hex but not in the low-surrogate range.
    extractor = _feed_all_with_timeout(['{"reply": "before \\ud83c\\u0041 after"}'])

    assert extractor.decoded == "before "
    assert extractor.done is True


def test_feeding_after_done_is_a_noop():
    extractor = _feed_all(['{"reply": "Hi."}'])
    assert extractor.done is True

    result = extractor.feed(', "more": "text"')

    assert result == ""
    assert extractor.decoded == "Hi."
