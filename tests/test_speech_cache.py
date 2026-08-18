"""services/speech_cache.py: in-memory handoff of pre-warmed TTS audio
Futures from services.conversation's streaming path to POST /voice/speak."""

from concurrent.futures import Future

from services import speech_cache


def _done_future(result):
    future = Future()
    future.set_result(result)
    return future


def test_create_then_pop_returns_the_entry_for_a_matching_language():
    speech_id = speech_cache.create("en", _done_future([b"first-chunk"]))

    entry = speech_cache.pop(speech_id, "en")

    assert entry is not None
    assert entry.language == "en"
    assert list(entry.audio_chunks()) == [b"first-chunk"]


def test_pop_is_single_use():
    speech_id = speech_cache.create("en", _done_future([b"chunk"]))

    first = speech_cache.pop(speech_id, "en")
    second = speech_cache.pop(speech_id, "en")

    assert first is not None
    assert second is None


def test_pop_returns_none_for_an_unknown_speech_id():
    assert speech_cache.pop("no-such-id", "en") is None


def test_pop_returns_none_and_discards_the_entry_on_a_language_mismatch():
    speech_id = speech_cache.create("en", _done_future([b"chunk"]))

    mismatched = speech_cache.pop(speech_id, "ar")
    retry = speech_cache.pop(speech_id, "en")

    assert mismatched is None
    # A mismatched pop still consumes the entry — each speech_id belongs to
    # exactly one turn's one expected /voice/speak call, so there's no
    # legitimate retry-with-a-different-language case to preserve it for.
    assert retry is None


def test_set_rest_attaches_the_rest_future_before_pop():
    speech_id = speech_cache.create("en", _done_future([b"first"]))
    speech_cache.set_rest(speech_id, _done_future([b"second", b"third"]))

    entry = speech_cache.pop(speech_id, "en")

    assert list(entry.audio_chunks()) == [b"first", b"second", b"third"]


def test_audio_chunks_yields_only_the_first_future_when_rest_was_never_set():
    speech_id = speech_cache.create("en", _done_future([b"only-chunk"]))

    entry = speech_cache.pop(speech_id, "en")

    assert list(entry.audio_chunks()) == [b"only-chunk"]


def test_set_rest_on_an_unknown_speech_id_is_a_noop():
    speech_cache.set_rest("no-such-id", _done_future([b"orphaned"]))  # must not raise


def test_expired_entries_are_swept_on_the_next_create(monkeypatch):
    fake_now = [1000.0]
    monkeypatch.setattr(speech_cache.time, "monotonic", lambda: fake_now[0])

    stale_id = speech_cache.create("en", _done_future([b"stale"]))

    fake_now[0] += speech_cache._TTL_SECONDS + 1  # advance past the TTL
    fresh_id = speech_cache.create("en", _done_future([b"fresh"]))  # triggers the sweep

    assert speech_cache.pop(stale_id, "en") is None
    assert speech_cache.pop(fresh_id, "en") is not None


def test_pop_rejects_an_expired_entry_even_without_an_intervening_create(monkeypatch):
    """The TTL must bound staleness on its own — a caller who pops a stale
    speech_id shouldn't get served just because no other turn happened to
    create() a new entry and trigger the opportunistic sweep in between."""
    fake_now = [1000.0]
    monkeypatch.setattr(speech_cache.time, "monotonic", lambda: fake_now[0])

    speech_id = speech_cache.create("en", _done_future([b"stale"]))
    fake_now[0] += speech_cache._TTL_SECONDS + 1

    assert speech_cache.pop(speech_id, "en") is None
