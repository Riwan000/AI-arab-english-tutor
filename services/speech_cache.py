"""Short-lived, in-memory handoff of pre-warmed TTS audio (as Futures) from
services.conversation's early-synthesis path over to the POST /voice/speak
route, so a reply that already started generating its first sentence's audio
during LLM streaming doesn't re-synthesize it from scratch once the frontend
asks for speech.

Only correct for a single-process deployment: entries live in process
memory, and this app runs a single uvicorn worker (see scripts/start_api.sh)
with no shared cache backing it. If that ever changes, this needs to move to
a shared store (e.g. Redis) instead.
"""

import time
import uuid
from collections.abc import Iterator
from concurrent.futures import Future
from threading import Lock

_TTL_SECONDS = 120


class SpeechCacheEntry:
    """Mutable slot: `rest_future` starts unset because the "rest" of the
    reply (and thus its audio) isn't known until the LLM stream finishes,
    which happens after `first_future` is already warming in the
    background."""

    def __init__(self, language: str, first_future: "Future[list[bytes]]", expires_at: float) -> None:
        self.language = language
        self.first_future = first_future
        self.rest_future: "Future[list[bytes]] | None" = None
        self.expires_at = expires_at

    def audio_chunks(self) -> Iterator[bytes]:
        """Blocks on whichever futures aren't done yet — usually close to
        instant, since both were submitted well before the frontend's
        /voice/speak request arrives."""
        yield from self.first_future.result()
        if self.rest_future is not None:
            yield from self.rest_future.result()


_lock = Lock()
_entries: dict[str, SpeechCacheEntry] = {}


def create(language: str, first_future: "Future[list[bytes]]") -> str:
    """Register a warming entry and return its speech_id. Call `set_rest`
    once the rest-of-reply future is known."""
    speech_id = uuid.uuid4().hex
    with _lock:
        _evict_expired()
        _entries[speech_id] = SpeechCacheEntry(
            language, first_future, time.monotonic() + _TTL_SECONDS
        )
    return speech_id


def set_rest(speech_id: str, rest_future: "Future[list[bytes]]") -> None:
    with _lock:
        entry = _entries.get(speech_id)
        if entry is not None:
            entry.rest_future = rest_future


def pop(speech_id: str, language: str) -> SpeechCacheEntry | None:
    """Consume the entry if present, unexpired, and matching the requested
    language. Popped so an entry is served at most once — a route caller who
    gets None here should fall back to synthesizing fresh, exactly as if
    this cache didn't exist."""
    with _lock:
        entry = _entries.pop(speech_id, None)
    if entry is None or entry.language != language or entry.expires_at < time.monotonic():
        return None
    return entry


def _evict_expired() -> None:
    """Best-effort sweep run opportunistically on insert — this app has no
    background scheduler, and entry volume is one-per-chat-turn, so an
    unpopped entry (frontend never called /voice/speak) just ages out on the
    next turn's create() instead of leaking forever."""
    now = time.monotonic()
    expired = [key for key, entry in _entries.items() if entry.expires_at < now]
    for key in expired:
        del _entries[key]
