"""Incrementally decodes the "reply" string field out of a streaming JSON
object, before the object has finished arriving.

The chat LLM is always prompted to return a single
{"reply": ..., "corrections": [...], "session_ending": ...} object with
"reply" listed — and modeled in the prompt's example — as the first key (see
prompts/system_prompt.yaml). That lets the start of "reply" be pulled out of
the raw JSON-escaped bytes as they stream in, so services.conversation can
kick off speech synthesis for the first sentence before the model has
finished generating the rest of the reply (and its corrections).

This is best-effort only: the reply/corrections the caller actually shows
the learner always come from parsing the complete accumulated response text
with services.grammar, exactly as before streaming existed. If this
extractor never finds a "reply" key, or hits an escape it doesn't recognize,
it just stops decoding — no exception, no effect beyond missing out on the
early-audio optimization for that turn.
"""

import re

_REPLY_KEY = re.compile(r'"reply"\s*:\s*"')

# Preamble ("{ ... up to the opening quote of "reply") should only ever be a
# handful of characters — bail out rather than buffering forever if "reply"
# never shows up (wrong key, model ignored the schema, etc).
_MAX_PREAMBLE = 200

_SIMPLE_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


class ReplyTextExtractor:
    """Stateful, chunk-at-a-time decoder for the "reply" field's JSON string
    value. Feed it raw text deltas in arrival order via `feed`."""

    def __init__(self) -> None:
        self._preamble = ""
        self._started = False
        self._finished = False
        self._carry = ""  # trailing partial escape sequence from the last feed()
        self.decoded = ""

    @property
    def done(self) -> bool:
        """True once the closing quote was seen, or decoding gave up."""
        return self._finished

    def feed(self, chunk: str) -> str:
        """Feed the next raw delta from the LLM stream. Returns the newly
        decoded plain-text characters (if any) contributed by this chunk."""
        if self._finished or not chunk:
            return ""

        if not self._started:
            chunk = self._consume_preamble(chunk)
            if chunk is None:
                return ""

        text = self._carry + chunk
        self._carry = ""
        new_text = self._decode(text)
        self.decoded += new_text
        return new_text

    def _consume_preamble(self, chunk: str) -> str | None:
        self._preamble += chunk
        match = _REPLY_KEY.search(self._preamble)
        if match is None:
            if len(self._preamble) > _MAX_PREAMBLE:
                self._finished = True
            return None
        self._started = True
        remainder = self._preamble[match.end() :]
        self._preamble = ""
        return remainder

    def _decode(self, text: str) -> str:
        out: list[str] = []
        i = 0
        n = len(text)
        # `not self._finished` is a deliberate second guard, not just `i < n`:
        # every give-up branch below must be able to stop the loop by setting
        # _finished, even one that (by mistake) leaves i unadvanced.
        while i < n and not self._finished:
            ch = text[i]

            if ch == '"':
                self._finished = True
                break

            if ch != "\\":
                out.append(ch)
                i += 1
                continue

            # Escape sequence — hold back an incomplete one for the next feed().
            if i + 1 >= n:
                self._carry = text[i:]
                break

            nxt = text[i + 1]
            if nxt == "u":
                consumed = self._decode_unicode_escape(text, i, out)
                if consumed is None:
                    self._carry = text[i:]
                    break
                if self._finished:
                    # A malformed \uXXXX (bad hex, unpaired/invalid surrogate)
                    # sets _finished with consumed == 0 — without this check
                    # i never advances and the next iteration re-decodes the
                    # exact same escape forever.
                    break
                i += consumed
                continue

            decoded_char = _SIMPLE_ESCAPES.get(nxt)
            if decoded_char is None:
                self._finished = True
                break
            out.append(decoded_char)
            i += 2

        return "".join(out)

    def _decode_unicode_escape(self, text: str, i: int, out: list[str]) -> int | None:
        """Decode a \\uXXXX escape at position i (possibly a surrogate pair
        continued by a second \\uXXXX). Returns the number of characters
        consumed, or None if the chunk ended mid-escape and more input is
        needed."""
        n = len(text)
        if i + 6 > n:
            return None
        try:
            code = int(text[i + 2 : i + 6], 16)
        except ValueError:
            self._finished = True
            return 0

        if 0xD800 <= code <= 0xDBFF:
            # High surrogate — a UTF-16 pair (e.g. flag emoji) needs the
            # following \uXXXX low surrogate to form one real character.
            if i + 12 > n:
                return None
            if text[i + 6 : i + 8] != "\\u":
                self._finished = True
                return 0
            try:
                low = int(text[i + 8 : i + 12], 16)
            except ValueError:
                self._finished = True
                return 0
            if not (0xDC00 <= low <= 0xDFFF):
                self._finished = True
                return 0
            code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
            out.append(chr(code))
            return 12

        out.append(chr(code))
        return 6
