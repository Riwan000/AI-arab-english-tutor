"""Grammar feedback data model."""

from pydantic import BaseModel, Field


class GrammarFeedback(BaseModel):
    """Structured correction from LLM — aligns with API chat response and db.md."""

    mistake_type: str
    wrong_text: str
    correct_text: str
    english_explanation: str
    arabic_explanation: str
    tip: str = ""
    message_index: int | None = Field(
        default=None,
        description="Index of the user message in session state (set when persisting)",
    )
