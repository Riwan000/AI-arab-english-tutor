"""Lesson data model."""

from pydantic import BaseModel


class Lesson(BaseModel):
    id: str
    title: str
    description: str
    examples: list[str] = []
    grammar_rules: list[str] = []
    allowed_vocabulary: list[str] = []
    negative_form: list[str] = []
    question_form: list[str] = []
    tips: list[str] = []
