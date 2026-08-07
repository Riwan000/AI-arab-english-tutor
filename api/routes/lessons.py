"""Lesson endpoints."""

from fastapi import APIRouter

from api.schemas.lesson import LessonsListResponse
from models.lesson import Lesson
from services import lessons

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.get("")
def list_all_lessons() -> dict:
    return LessonsListResponse.from_summaries(lessons.list_lessons())


@router.get("/{lesson_id}", response_model=Lesson)
def get_lesson_detail(lesson_id: str) -> Lesson:
    return lessons.get_lesson(lesson_id)
