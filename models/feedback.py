"""Grammar feedback data model."""

from pydantic import BaseModel


class GrammarFeedback(BaseModel):
    mistake_type: str
    wrong_text: str
    correct_text: str
    english_explanation: str
    arabic_explanation: str
    tip: str = ""
