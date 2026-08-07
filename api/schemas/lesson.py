"""Lesson API schemas."""

from models.lesson import Lesson, LessonSummary


class LessonsListResponse:
    """Wrapper for GET /api/v1/lessons — use dict in routes for OpenAPI clarity."""

    @staticmethod
    def from_summaries(lessons: list[LessonSummary]) -> dict:
        return {"lessons": [lesson.model_dump() for lesson in lessons]}


# Re-export domain models used as response bodies
LessonDetail = Lesson
LessonSummarySchema = LessonSummary
