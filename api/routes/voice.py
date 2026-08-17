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
from services import usage, voice
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


@router.post("/speak")
def speak(
    body: SpeakRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:

    usage.check_and_increment_voice(current_user.id)

    chunks = voice.synthesize_speech_stream(
        body.text,
        language=body.language,
    )

    # Pull the first chunk now, while we're still free to return a normal
    # error response — once StreamingResponse starts sending, the 200 status
    # is already committed and a mid-stream failure can only truncate audio.
    first_chunk = next(chunks)

    return StreamingResponse(
        chain([first_chunk], chunks),
        media_type="audio/mpeg",
    )