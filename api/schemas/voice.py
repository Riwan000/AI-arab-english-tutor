"""Voice API schemas."""

from typing import Literal
from typing import TypedDict

from pydantic import BaseModel, Field

MAX_SPEAK_TEXT_LENGTH = 3000
MAX_AUDIO_UPLOAD_BYTES = 10 * 1024 * 1024  # ~10MB / 60s cap


class TranscribeResponse(BaseModel):
    text: str
    language: Literal["en", "ar"]


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SPEAK_TEXT_LENGTH)
    language: Literal["en", "ar"] = "en"

class TranscriptionResult(TypedDict):
    text: str
    language: str