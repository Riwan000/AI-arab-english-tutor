"""Voice API schemas."""

from typing import Literal

from pydantic import BaseModel, Field

MAX_SPEAK_TEXT_LENGTH = 500
MAX_AUDIO_UPLOAD_BYTES = 10 * 1024 * 1024  # ~10MB / 60s cap


class TranscribeResponse(BaseModel):
    text: str


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SPEAK_TEXT_LENGTH)
    language: Literal["en", "ar"] = "en"
