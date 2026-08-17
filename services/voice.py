"""ElevenLabs voice client: Scribe v2 STT and multilingual TTS."""

import os

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

def synthesize_speech(
    text: str,
    language: str = "en",
) -> bytes:

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
        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            text=text,
        )

        return b"".join(audio)

    except Exception as exc:
        raise VoiceSynthesisError(
            f"ElevenLabs synthesis error: {exc}"
        ) from exc