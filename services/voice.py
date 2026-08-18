"""ElevenLabs voice client: Scribe v2 STT and multilingual TTS."""

import os
import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

from elevenlabs.client import ElevenLabs

from services.errors import VoiceSynthesisError, VoiceTranscriptionError

# The authoritative value is Settings.elevenlabs_api_key (api/config.py),
# injected here by api/main.py's lifespan the same way OPENROUTER_API_KEY is
# synced into services/openrouter.py. The os.getenv() fallback below only
# covers module import, which happens before that lifespan wiring runs.
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")


def build_client(api_key: str) -> ElevenLabs | None:
    """Construct the ElevenLabs client, or None when no key is configured."""
    return ElevenLabs(api_key=api_key) if api_key else None


client = build_client(ELEVENLABS_API_KEY)


# ---------------------------------------------------------------------------
# Voice configuration
# ---------------------------------------------------------------------------

# Put the voice IDs you choose from the ElevenLabs Voices API here.
#
# Example:
#
# ENGLISH_VOICE_ID = "..."
# ARABIC_VOICE_ID = "..."
#
# We will get these IDs from the /v2/voices endpoint using
# language filtering.

ENGLISH_VOICE_ID = os.getenv("ELEVENLABS_ENGLISH_VOICE_ID", "")
ARABIC_VOICE_ID = os.getenv("ELEVENLABS_ARABIC_VOICE_ID", "")

VOICE_MAP = {
    "en": ENGLISH_VOICE_ID,
    "ar": ARABIC_VOICE_ID,
}


# ---------------------------------------------------------------------------
# Speech-to-Text
# ---------------------------------------------------------------------------

def transcribe_audio(
    audio_bytes: bytes,
    mimetype: str,
) -> tuple[str, str]:

    if client is None:
        raise VoiceTranscriptionError(
            "ElevenLabs API key not configured. "
            "Add ELEVENLABS_API_KEY to .env"
        )

    try:
        result = client.speech_to_text.convert(
            file=audio_bytes,
            model_id="scribe_v2",
        )

    except Exception as exc:
        raise VoiceTranscriptionError(
            f"ElevenLabs transcription error: {exc}"
        ) from exc

    try:
        transcript = result.text
    except AttributeError as exc:
        raise VoiceTranscriptionError(
            "ElevenLabs returned an unexpected response"
        ) from exc

    if not isinstance(transcript, str):
        raise VoiceTranscriptionError(
            "ElevenLabs returned an unexpected response"
        )

    # Scribe returns the detected language.
    detected_language = getattr(
        result,
        "language_code",
        None,
    )

    if detected_language:
        if detected_language.startswith("ar"):
            language = "ar"

        elif detected_language.startswith("en"):
            language = "en"

        else:
            raise VoiceTranscriptionError(
                f"Unsupported detected language: {detected_language}"
            )

    else:
        raise VoiceTranscriptionError(
            "ElevenLabs did not return a detected language"
        )

    return transcript, language


# ---------------------------------------------------------------------------
# Find available voices
# ---------------------------------------------------------------------------

def get_voices(language: str):
    """
    Get ElevenLabs voices matching a language.

    language:
        "en" -> English voices
        "ar" -> Arabic voices
    """

    if client is None:
        raise VoiceSynthesisError(
            "ElevenLabs API key not configured. "
            "Add ELEVENLABS_API_KEY to .env"
        )

    if language not in {"en", "ar"}:
        raise VoiceSynthesisError(
            f"Unsupported language: {language}"
        )

    try:
        response = client.voices.search(
            language=[language],
            page_size=100,
        )

        return response.voices

    except Exception as exc:
        raise VoiceSynthesisError(
            f"Could not retrieve ElevenLabs voices: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Text-to-Speech
# ---------------------------------------------------------------------------

def synthesize_speech_stream(
    text: str,
    language: str = "en",
) -> Iterator[bytes]:
    """Stream synthesized speech as MP3 chunks as ElevenLabs generates them,
    so callers can start playback before the full clip is ready."""

    if client is None:
        raise VoiceSynthesisError(
            "ElevenLabs API key not configured. "
            "Add ELEVENLABS_API_KEY to .env"
        )

    if language not in VOICE_MAP:
        raise VoiceSynthesisError(
            f"Unsupported language: {language}"
        )

    voice_id = VOICE_MAP[language]

    if not voice_id:
        raise VoiceSynthesisError(
            f"No ElevenLabs voice configured for language: {language}. "
            f"Add the voice ID to your .env file."
        )

    try:
        yield from client.text_to_speech.stream(
            voice_id=voice_id,
            model_id="eleven_flash_v2_5",
            text=text,
            # 3 = max latency optimization while keeping the text normalizer
            # on (level 4 turns normalization off, which risks mispronouncing
            # numbers/dates — not an acceptable tradeoff for a tutor app).
            optimize_streaming_latency=3,
        )

    except Exception as exc:
        raise VoiceSynthesisError(
            f"ElevenLabs synthesis error: {exc}"
        ) from exc


def synthesize_speech_stream_to_list(text: str, language: str = "en") -> list[bytes]:
    """Fully drain synthesize_speech_stream into a list. Exists so
    services.conversation can hand this straight to a ThreadPoolExecutor as
    a plain (fn, *args) submission — a background thread needs a concrete
    result to store on its Future, not a lazy generator that would otherwise
    still be doing its (blocking) ElevenLabs I/O on demand later, off-thread."""
    return list(synthesize_speech_stream(text, language))


# Public so services.conversation can apply the identical boundary rule to
# text streaming in from the LLM — using the same regex is what guarantees
# the sentence synthesized early during streaming matches the first sentence
# _split_first_sentence would find in the final, complete reply text.
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?؟])\s+(?=\S)")


def split_first_sentence(text: str) -> tuple[str, str] | None:
    """Split off the first sentence, or None if there's no detectable
    boundary (single sentence, no terminal punctuation, etc.). Public so
    services.conversation can compute the identical "rest of the reply" text
    its early speech-warming path uses, keeping exactly one source of truth
    for where a reply gets split for TTS."""
    parts = [part for part in SENTENCE_BOUNDARY.split(text) if part.strip()]
    if len(parts) <= 1:
        return None
    return parts[0], " ".join(parts[1:])


def synthesize_speech_stream_pipelined(
    text: str,
    language: str = "en",
) -> Iterator[bytes]:
    """Like synthesize_speech_stream, but starts streaming the first
    sentence's audio while synthesizing the rest of the reply concurrently
    in the background, so playback can start sooner without needing a
    second /speak request (and a second voice-quota charge) to do it."""

    split = split_first_sentence(text)
    if split is None:
        yield from synthesize_speech_stream(text, language)
        return

    first, rest = split

    with ThreadPoolExecutor(max_workers=1) as executor:
        rest_future = executor.submit(lambda: list(synthesize_speech_stream(rest, language)))

        yield from synthesize_speech_stream(first, language)
        yield from rest_future.result()