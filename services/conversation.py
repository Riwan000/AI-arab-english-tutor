"""Chat orchestration — no HTTP, no UI, no direct DB access from routes."""

import os
from concurrent.futures import ThreadPoolExecutor

from models.conversation import ChatResponse, SessionSummary
from models.feedback import GrammarFeedback
from prompts.prompt_builder import build_messages, format_past_context
from repositories.draft_repo import DraftRepository
from repositories.session_repo import SessionRepository
from services import grammar, lessons, openrouter, scoring, speech_cache, voice
from services.streaming_json import ReplyTextExtractor

# Persistent (not context-managed) so a "rest of the reply" synthesis kicked
# off here can keep running in the background after send_message/
# start_conversation already returned their response to the route — the
# whole point is that it finishes before the frontend's later /voice/speak
# call, not before this module's own functions return.
_SPEECH_WARM_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="speech-warm")


def _stream_reply_and_warm_speech(messages: list[dict], language: str) -> tuple[str, str | None]:
    """Streams the LLM turn, best-effort warming TTS for the reply's first
    sentence as soon as it's decoded from the stream — so services.voice can
    skip re-synthesizing it once the frontend asks for speech. Returns the
    complete accumulated raw response text (identical to what
    openrouter.chat_completion would have returned) plus a speech_id to hand
    back to the caller, or None if no warming happened (e.g. a single-
    sentence reply with no detectable boundary — the frontend's /voice/speak
    call falls back to synthesizing from scratch exactly as it did before
    this existed).

    Only the *first* sentence is warmed here, from ReplyTextExtractor's
    running decode — that's safe because decoding either fully succeeds or
    gives up without ever producing a wrong character, so a prefix it has
    already decoded is always correct. The "rest" of the reply is
    deliberately NOT warmed from that same buffer: if extraction gives up
    partway through (a malformed \\uXXXX escape, for instance), the buffer
    would be truncated relative to the real reply, and warming from it would
    hand the frontend audio that's shorter than the text it displays. Call
    _warm_rest_of_reply() instead, once grammar.parse_response has produced
    the actual, complete reply text.
    """
    raw_parts: list[str] = []
    extractor = ReplyTextExtractor()
    speech_id: str | None = None

    for delta in openrouter.chat_completion_stream(messages):
        raw_parts.append(delta)
        if not extractor.done:
            extractor.feed(delta)
            if speech_id is None:
                match = voice.SENTENCE_BOUNDARY.search(extractor.decoded)
                if match:
                    first_sentence = extractor.decoded[: match.start()]
                    future = _SPEECH_WARM_EXECUTOR.submit(
                        voice.synthesize_speech_stream_to_list, first_sentence, language
                    )
                    speech_id = speech_cache.create(language, future)

    return "".join(raw_parts), speech_id


def _warm_rest_of_reply(speech_id: str, reply: str, language: str) -> None:
    """Warm TTS for whatever follows the first sentence, using the final,
    fully-parsed reply text — never the streaming extractor's buffer (see
    _stream_reply_and_warm_speech's docstring for why). split_first_sentence
    uses the identical boundary rule the extractor already applied, so
    `split[0]` here is guaranteed to match the first-sentence text that was
    already submitted for warming."""
    split = voice.split_first_sentence(reply)
    if split is None:
        return
    rest = split[1]
    rest_future = _SPEECH_WARM_EXECUTOR.submit(
        voice.synthesize_speech_stream_to_list, rest, language
    )
    speech_cache.set_rest(speech_id, rest_future)


def start_conversation(
    lesson_id: str | None,
    difficulty: str = "beginner",
    mode: str = "lesson",
    user_id: int | None = None,
    language: str = "en",
) -> ChatResponse:
    """Build start prompt, call LLM, return clean reply. Loads a lesson only in lesson mode."""
    lesson_dict = _resolve_lesson(lesson_id, mode)

    past_context = None
    if mode == "free_talk" and user_id is not None:
        past_profile = SessionRepository().get_user_learning_profile(user_id)
        past_context = format_past_context(past_profile)

    messages = build_messages(
        lesson_dict,
        [],
        start=True,
        difficulty=difficulty,
        mode=mode,
        past_context=past_context,
    )
    raw, speech_id = _stream_reply_and_warm_speech(messages, language)
    reply, corrections = grammar.parse_response(raw)
    if speech_id is not None:
        _warm_rest_of_reply(speech_id, reply, language)

    return ChatResponse(reply=reply, corrections=corrections, speech_id=speech_id)


def send_message(
    lesson_id: str | None,
    messages: list[dict],
    user_text: str,
    difficulty: str = "beginner",
    mode: str = "lesson",
    user_id: int | None = None,
    language: str = "en",
) -> ChatResponse:
    """Append user message, call LLM, parse corrections, return clean reply."""
    lesson_dict = _resolve_lesson(lesson_id, mode)

    past_context = None
    if mode == "free_talk" and user_id is not None:
        past_profile = SessionRepository().get_user_learning_profile(user_id)
        past_context = format_past_context(past_profile)

    history = [*messages, {"role": "user", "content": user_text}]
    prompt_messages = build_messages(
        lesson_dict,
        history,
        difficulty=difficulty,
        mode=mode,
        past_context=past_context,
    )
    raw, speech_id = _stream_reply_and_warm_speech(prompt_messages, language)
    reply, corrections = grammar.parse_response(raw)
    if speech_id is not None:
        _warm_rest_of_reply(speech_id, reply, language)

    # OR'd with a cheap keyword fallback so an obvious "bye" still ends the
    # conversation even if the model forgets to set the JSON flag.
    session_ending = grammar.extract_session_ending(raw) or grammar.contains_farewell_keyword(
        user_text
    )

    if mode == "free_talk" and user_id is not None:
        if session_ending:
            # The conversation is finishing — it'll be finalized into a
            # completed session via end_session, so don't leave a stale draft.
            DraftRepository().delete(user_id)
        else:
            DraftRepository().save(
                user_id,
                messages=[*history, {"role": "assistant", "content": reply}],
                lesson_id=lesson_id,
                mode=mode,
                difficulty=difficulty,
            )

    return ChatResponse(
        reply=reply, corrections=corrections, session_ending=session_ending, speech_id=speech_id
    )



def _resolve_lesson(lesson_id: str | None, mode: str) -> dict | None:
    """Look up the lesson in lesson mode only — Free Talk has no lesson to resolve."""
    if mode != "lesson":
        return None
    lesson = lessons.get_lesson(lesson_id)
    return lesson.model_dump()


def end_session(
    lesson_id: str | None,
    messages: list[dict],
    mistakes: list,
    mode: str = "lesson",
    user_id: int | None = None,
) -> SessionSummary | None:
    """Score session, persist via repository, return summary. Free Talk has no lesson to look up."""
    if not messages:
        return None

    if mode == "free_talk":
        lesson_dict, lesson_title = None, "Free Talk"
    else:
        lesson = lessons.get_lesson(lesson_id)
        lesson_dict, lesson_title = lesson.model_dump(), lesson.title

    summary = scoring.calculate_session_summary(
        messages=messages,
        mistakes=mistakes,
        lesson_title=lesson_title,
    )

    conversation_id = SessionRepository().save(
        lesson=lesson_dict or {"id": None, "title": "Free Talk"},
        messages=messages,
        mistakes=mistakes,
        summary=summary,
        model_used=os.getenv("DEFAULT_MODEL", openrouter.DEFAULT_MODEL),
        user_id=user_id,
        mode=mode,
    )

    if conversation_id is None:
        return None

    if user_id is not None:
        # Now finalized into a completed session — clear the draft so it
        # isn't offered for resume again (idempotent if none existed).
        DraftRepository().delete(user_id)

    return SessionSummary(
        id=conversation_id,
        grammar_score=summary["grammar"],
        exchange_count=summary["exchanges"],
        mistake_count=summary["mistake_count"],
        vocabulary=summary.get("vocabulary", []),
        recommendation=summary.get("recommendation"),
        mistake_types=summary.get("mistake_types", []),
    )
