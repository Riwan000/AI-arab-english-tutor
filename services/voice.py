"""Deepgram voice client: Nova-3 speech-to-text and Aura text-to-speech."""

import os

import httpx
from dotenv import load_dotenv

from services.errors import VoiceSynthesisError, VoiceTranscriptionError

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_BASE_URL = "https://api.deepgram.com/v1"


def transcribe_audio(audio_bytes: bytes, mimetype: str) -> str:
    if not DEEPGRAM_API_KEY:
        raise VoiceTranscriptionError("Deepgram API key not configured. Add DEEPGRAM_API_KEY to .env")

    try:
        response = httpx.post(
            f"{DEEPGRAM_BASE_URL}/listen",
            params={"model": "nova-3", "smart_format": "true"},
            headers={
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type": mimetype,
            },
            content=audio_bytes,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise VoiceTranscriptionError("Transcription took too long. Please try again.")
    except httpx.HTTPStatusError as exc:
        raise VoiceTranscriptionError(f"Deepgram transcription error: {exc.response.status_code}")
    except httpx.RequestError:
        raise VoiceTranscriptionError("Could not reach the transcription service")
    except ValueError:
        raise VoiceTranscriptionError("Deepgram returned an unexpected response")

    try:
        transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError, TypeError):
        raise VoiceTranscriptionError("Deepgram returned an unexpected response")

    if not isinstance(transcript, str):
        raise VoiceTranscriptionError("Deepgram returned an unexpected response")

    return transcript


def synthesize_speech(text: str, voice: str = "aura-asteria-en") -> bytes:
    if not DEEPGRAM_API_KEY:
        raise VoiceSynthesisError("Deepgram API key not configured. Add DEEPGRAM_API_KEY to .env")

    try:
        response = httpx.post(
            f"{DEEPGRAM_BASE_URL}/speak",
            params={"model": voice},
            headers={
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"text": text},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.content
    except httpx.TimeoutException:
        raise VoiceSynthesisError("Speech synthesis took too long. Please try again.")
    except httpx.HTTPStatusError as exc:
        raise VoiceSynthesisError(f"Deepgram synthesis error: {exc.response.status_code}")
    except httpx.RequestError:
        raise VoiceSynthesisError("Could not reach the speech synthesis service")
