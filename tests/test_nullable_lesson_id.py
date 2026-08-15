from api.schemas.session import SessionCreateRequest
from models.conversation import Conversation, SessionDetail, SessionListItem


def test_session_list_item_accepts_null_lesson_id():
    item = SessionListItem(id=1, lesson_id=None, lesson_title="Free Talk", ended_at="now")
    assert item.lesson_id is None


def test_session_detail_accepts_null_lesson_id():
    detail = SessionDetail(
        id=1,
        lesson_id=None,
        lesson_title="Free Talk",
        grammar_score=90,
        exchange_count=2,
        mistake_count=0,
    )
    assert detail.lesson_id is None


def test_conversation_accepts_null_lesson_id():
    convo = Conversation(lesson_id=None)
    assert convo.lesson_id is None


def test_session_create_request_defaults_lesson_id_to_none():
    request = SessionCreateRequest(messages=[{"role": "user", "content": "hi"}])
    assert request.lesson_id is None


def test_session_create_request_still_accepts_a_lesson_id():
    request = SessionCreateRequest(
        lesson_id="present_simple",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert request.lesson_id == "present_simple"
