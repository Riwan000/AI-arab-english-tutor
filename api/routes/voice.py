"""Voice endpoints: speech-to-text transcription and text-to-speech synthesis."""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

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
) -> Response:

    usage.check_and_increment_voice(current_user.id)

    audio_bytes = voice.synthesize_speech(
        body.text,
        language=body.language,
    )

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
    )