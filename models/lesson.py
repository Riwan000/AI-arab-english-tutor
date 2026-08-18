"""Lesson data models."""

from pydantic import BaseModel, Field


class LessonSummary(BaseModel):
    """Subset returned by GET /api/v1/lessons."""

    id: str
    title: str
    description: str


class Lesson(BaseModel):
    """Full lesson detail for GET /api/v1/lessons/{lesson_id}."""

    id: str
    title: str
    description: str
    examples: list[str] = Field(default_factory=list)
    grammar_rules: list[str] = Field(default_factory=list)
    allowed_vocabulary: list[str] = Field(default_factory=list)
    negative_form: list[str] = Field(default_factory=list)
    question_form: list[str] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list)
    question_types: list[str] = Field(default_factory=list)

    def to_summary(self) -> LessonSummary:
        return LessonSummary(id=self.id, title=self.title, description=self.description)
