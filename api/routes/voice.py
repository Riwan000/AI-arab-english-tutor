"""Voice endpoints: speech-to-text transcription and text-to-speech synthesis."""

from itertools import chain

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse

from api.dependencies import get_current_user
from api.schemas.voice import (
    MAX_AUDIO_UPLOAD_BYTES,
    SpeakRequest,
    TranscribeResponse,
)
from models.user import User
from services import speech_cache, usage, voice
from services.errors import AudioTooLargeError

router = APIRouter(prefix="/voice", tags=["voice"])

_READ_CHUNK_BYTES = 64 * 1024


async def _read_upload_capped(
    upload: UploadFile,
    max_bytes: int,
) -> bytes:
    """Read an upload in bounded chunks, aborting before buffering past max_bytes."""
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = await upload.read(_READ_CHUNK_BYTES)

        if not chunk:
            break

        total += len(chunk)

        if total > max_bytes:
            raise AudioTooLargeError()

        chunks.append(chunk)

    return b"".join(chunks)


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
)
async def transcribe(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> TranscribeResponse:

    audio_bytes = await _read_upload_capped(
        audio,
        MAX_AUDIO_UPLOAD_BYTES,
    )

    usage.check_and_increment_voice(current_user.id)

    text, language = voice.transcribe_audio(
    audio_bytes,
    audio.content_type or "audio/wav",
    )


    return TranscribeResponse(
    text=text,
    language=language,
    )


def _first_chunk_of(body: SpeakRequest):
    """Resolve the audio-chunk iterator to stream back, plus its first chunk
    pulled eagerly (while we're still free to return a normal error response
    instead of a truncated 200 stream).

    Prefers speech_cache's pre-warmed audio when body.speech_id names a live
    entry. If that warmed synthesis itself failed — a transient ElevenLabs
    error while it was running in the background is the expected case
    (VoiceSynthesisError), but anything else raised on that background
    thread (e.g. the executor itself misbehaving) is caught too, on purpose:
    the cache is purely an optimization, so any way it can fail should fall
    back to synthesizing body.text fresh — the same thing that happens on a
    cache miss — rather than surfacing a failure the frontend has no way to
    know was avoidable.
    """
    cached = speech_cache.pop(body.speech_id, body.language) if body.speech_id else None
    if cached is not None:
        try:
            chunks = cached.audio_chunks()
            return chunks, next(chunks)
        except Exception:
            pass

    chunks = voice.synthesize_speech_stream_pipelined(body.text, language=body.language)
    return chunks, next(chunks)


@router.post("/speak")
def speak(
    body: SpeakRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:

    usage.check_and_increment_voice(current_user.id)

    chunks, first_chunk = _first_chunk_of(body)

    return StreamingResponse(
        chain([first_chunk], chunks),
        media_type="audio/mpeg",
    )