"""Main chat interface for guided AI conversation."""

from datetime import datetime, timezone

import streamlit as st

import api_client
import i18n
from components.correction_card import render_correction_card


def render_chat() -> None:
    lesson = st.session_state.get("lesson")
    if st.session_state.mode == "lesson" and not lesson:
        st.warning(i18n.t("choose_lesson_warning"))
        return

    st.header(
        i18n.t("training_header_lesson", title=lesson["title"])
        if lesson
        else i18n.t("training_header_free_talk")
    )

    played_index = st.session_state.get("_last_played_audio_index", -1)
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("feedback"):
                render_correction_card(message["feedback"], key_prefix=f"msg{idx}")
            if message.get("audio_reply") and idx > played_index:
                st.audio(message["audio_reply"], autoplay=True)
                st.session_state["_last_played_audio_index"] = idx

    limit_reached = st.session_state.get("daily_limit_reached", False)

    if not st.session_state.messages and not limit_reached:
        _start_conversation(lesson)

    if not limit_reached:
        _handle_voice_input(lesson)

    if prompt := st.chat_input(
        i18n.t("daily_limit_placeholder") if limit_reached else i18n.t("chat_input_placeholder"),
        disabled=limit_reached,
    ):
        _handle_user_message(prompt, lesson)


def _message_metadata(lesson: dict | None) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lesson_id": lesson["id"] if lesson else None,
    }


def _start_conversation(lesson: dict | None) -> None:
    result = api_client.start_chat(
        lesson_id=lesson["id"] if lesson else None,
        difficulty=st.session_state.get("difficulty") or "beginner",
        mode=st.session_state.get("mode") or "lesson",
    )
    if not result.get("reply"):
        if st.session_state.get("daily_limit_reached"):
            # This call is what just set the flag — rerun so the chat_input
            # below reflects it now instead of on the next unrelated rerun.
            st.rerun()
        return

    assistant_message = {
        "role": "assistant",
        "content": result["reply"],
        "has_correction": False,
        **_message_metadata(lesson),
    }
    st.session_state.messages.append(assistant_message)
    st.rerun()


def _handle_voice_input(lesson: dict | None) -> None:
    audio = st.audio_input(i18n.t("voice_input_label"), key="voice_input")
    if audio is None:
        return

    # st.audio_input keeps returning the same UploadedFile across reruns
    # until the learner re-records, unlike mic_recorder's just_once=True —
    # so track the last-processed file_id ourselves to avoid resending it.
    if audio.file_id == st.session_state.get("_last_voice_file_id"):
        return
    st.session_state["_last_voice_file_id"] = audio.file_id

    text = api_client.transcribe_audio(audio.getvalue(), mimetype=audio.type or "audio/wav")
    if text:
        _handle_user_message(text, lesson, speak_reply=True)


def _handle_user_message(user_text: str, lesson: dict | None, speak_reply: bool = False) -> None:
    st.session_state.messages.append({
        "role": "user",
        "content": user_text,
        **_message_metadata(lesson),
    })
    user_message_index = len(st.session_state.messages) - 1

    result = api_client.send_message(
        lesson_id=lesson["id"] if lesson else None,
        messages=st.session_state.messages[:-1],
        user_text=user_text,
        difficulty=st.session_state.get("difficulty") or "beginner",
        mode=st.session_state.get("mode") or "lesson",
    )
    if not result.get("reply"):
        st.session_state.messages.pop()
        if st.session_state.get("daily_limit_reached"):
            # This call is what just set the flag — rerun so chat_input
            # disables now instead of accepting one more stray submission.
            st.rerun()
        return

    feedback = result.get("corrections", [])
    if feedback:
        for entry in feedback:
            entry["message_index"] = user_message_index
            st.session_state.mistakes.append(entry)

    assistant_message = {
        "role": "assistant",
        "content": result["reply"],
        "feedback": feedback,
        "has_correction": bool(feedback),
        **_message_metadata(lesson),
    }
    if speak_reply:
        assistant_message["audio_reply"] = api_client.synthesize_speech(result["reply"], "en")
    st.session_state.messages.append(assistant_message)
    st.rerun()
