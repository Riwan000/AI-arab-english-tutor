"""Load and cache static lesson JSON files."""

import json
from pathlib import Path

from models.lesson import Lesson, LessonSummary
from services.errors import LessonNotFoundError

LESSONS_DIR = Path(__file__).parent.parent / "lessons"
_lessons_cache: dict[str, Lesson] | None = None


def _load_all() -> dict[str, Lesson]:
    global _lessons_cache
    if _lessons_cache is not None:
        return _lessons_cache

    lessons: dict[str, Lesson] = {}
    for path in sorted(LESSONS_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            lesson = Lesson(**json.load(f))
        lessons[lesson.id] = lesson

    _lessons_cache = lessons
    return lessons


def list_lessons() -> list[LessonSummary]:
    return [lesson.to_summary() for lesson in _load_all().values()]


def get_lesson(lesson_id: str) -> Lesson:
    lesson = _load_all().get(lesson_id)
    if lesson is None:
        raise LessonNotFoundError()
    return lesson
