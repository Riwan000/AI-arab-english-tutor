"""Main chat interface for guided AI conversation."""

from datetime import datetime, timezone

import streamlit as st
import streamlit.components.v1 as components

import api_client
import i18n
from components.correction_card import render_correction_card

# Grammarly (and similar writing-assistant extensions) auto-inject an icon
# into any textarea it detects, including st.chat_input's — which sits right
# where VOICE_INPUT_DOCK_CSS docks the mic button, so the two visually
# collide. `data-gramm="false"` is the attribute Grammarly's content script
# checks before injecting; setting it opts this textarea out. st.markdown
# strips <script> tags, so this runs via components.html instead, which
# renders in a same-origin iframe and can reach the real page through
# window.parent. The textarea may not exist yet on first paint (chat_input
# mounts independently of this call), so a MutationObserver waits for it;
# it disconnects itself once found or after 5s so it never lingers.
GRAMMARLY_SUPPRESS_JS = """
<script>
(function () {
    function markNoGrammarly() {
        const ta = window.parent.document.querySelector('[data-testid="stChatInput"] textarea');
        if (!ta) return false;
        ta.setAttribute('data-gramm', 'false');
        ta.setAttribute('data-gramm_editor', 'false');
        ta.setAttribute('data-enable-grammarly', 'false');
        return true;
    }
    if (markNoGrammarly()) return;
    const observer = new MutationObserver(() => {
        if (markNoGrammarly()) observer.disconnect();
    });
    observer.observe(window.parent.document.body, {childList: true, subtree: true});
    setTimeout(() => observer.disconnect(), 5000);
})();
</script>
"""

# Docks the st.audio_input widget (key="voice_input") next to st.chat_input's
# send button as a compact mic icon. st.chat_input always renders in
# Streamlit's own sticky bottom bar while st.audio_input renders in normal
# flow, so there's no DOM-level way to put them in the same row — this
# fixed-positions the audio_input over the chat_input row instead. It must be
# `position: fixed` (viewport-relative), not `absolute` anchored to
# stMainBlockContainer: that container's height grows with the chat history,
# so a container-relative offset drifts out of alignment as messages pile up.
# stMainBlockContainer's right edge always coincides with the viewport's
# right edge (no sidebar margin on that side), so a fixed `right` offset
# still lines up with stBottomBlockContainer's width/padding. When recording
# starts, Streamlit swaps the record button's aria-label to "Stop"; that flip
# is used as a pure-CSS hook to expand the widget so the live waveform/timer
# take over the input row (capped below full viewport width so it clears the
# sidebar instead of running under it).
VOICE_INPUT_DOCK_CSS = """
<style>
.st-key-voice_input {
    position: fixed;
    right: 139px;
    bottom: 41px;
    width: 40px;
    z-index: 999;
    transition: width 0.25s ease;
}
.st-key-voice_input [data-testid="stWidgetLabel"],
.st-key-voice_input [data-testid="stElementToolbar"],
.st-key-voice_input [data-testid="stAudioInputWaveSurfer"],
.st-key-voice_input [data-testid="stAudioInputWaveformTimeCode"] {
    display: none;
}
.st-key-voice_input [data-testid="stAudioInput"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    min-height: unset !important;
}
.st-key-voice_input [data-testid="stAudioInput"] > div:last-child {
    justify-content: flex-end !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}
/* Streamlit wraps the record button in its own div sized ~52px regardless
   of the button's own width/height, so without this the wrapper overflows
   the 40px-wide flex-end row and the button's circle renders off-center,
   clipped by whatever sits to its left. */
.st-key-voice_input [data-testid="stAudioInput"] > div:last-child > div:has(> button[data-testid="stAudioInputActionButton"]) {
    width: 40px !important;
    height: 40px !important;
    min-width: 40px !important;
    min-height: 40px !important;
}
.st-key-voice_input button[data-testid="stAudioInputActionButton"] {
    background: #fdba74;
    border-radius: 50%;
    width: 40px !important;
    height: 40px !important;
    color: #5a2c0a;
    transition: background-color 0.15s ease, box-shadow 0.15s ease;
}
.st-key-voice_input:has(button[aria-label="Stop"]) {
    width: min(600px, calc(100vw - 320px));
    right: 0;
}
.st-key-voice_input:has(button[aria-label="Stop"]) button[data-testid="stAudioInputActionButton"] {
    background: #ea580c;
    color: #fff8f2;
    box-shadow: 0 0 0 4px rgba(234, 88, 12, 0.18);
}
@media (prefers-reduced-motion: no-preference) {
    .st-key-voice_input:has(button[aria-label="Stop"]) button[data-testid="stAudioInputActionButton"] {
        animation: mic-pulse 1.4s ease-in-out infinite;
    }
}
@keyframes mic-pulse {
    0%, 100% { box-shadow: 0 0 0 4px rgba(234, 88, 12, 0.18); }
    50% { box-shadow: 0 0 0 8px rgba(234, 88, 12, 0.08); }
}
.st-key-voice_input:has(button[aria-label="Stop"]) [data-testid="stAudioInputWaveSurfer"],
.st-key-voice_input:has(button[aria-label="Stop"]) [data-testid="stAudioInputWaveformTimeCode"] {
    display: block !important;
}
</style>
"""

# Auto-arms the mic once the assistant's autoplaying TTS reply finishes, so
# the learner can just start talking back instead of clicking the mic button
# every turn. A synthetic .click() only starts getUserMedia without a fresh
# user gesture because Chrome/Firefox waive that requirement once mic
# permission has already been granted for the origin (from the learner's
# first manual click) — so this is a no-op prompt on the very first turn but
# works silently on every turn after.
AUTO_RECORD_JS = """
<script>
(function () {
    function armAutoRecord() {
        const doc = window.parent.document;
        const audio = doc.querySelector('audio[autoplay]');
        if (!audio) return false;
        if (audio.dataset.autoRecordArmed) return true;
        audio.dataset.autoRecordArmed = 'true';
        audio.addEventListener('ended', function () {
            const micButton = doc.querySelector(
                '.st-key-voice_input button[data-testid="stAudioInputActionButton"]'
            );
            if (micButton && micButton.getAttribute('aria-label') !== 'Stop') {
                micButton.click();
            }
        }, { once: true });
        return true;
    }
    if (armAutoRecord()) return;
    const observer = new MutationObserver(() => {
        if (armAutoRecord()) observer.disconnect();
    });
    observer.observe(window.parent.document.body, {childList: true, subtree: true});
    setTimeout(() => observer.disconnect(), 5000);
})();
</script>
"""


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
    components.html(GRAMMARLY_SUPPRESS_JS, height=0)

    played_index = st.session_state.get("_last_played_audio_index", -1)
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("feedback"):
                render_correction_card(message["feedback"], key_prefix=f"msg{idx}")
            if message.get("needs_audio") and idx > played_index:
                # Synthesized here rather than before the message was appended,
                # so the reply text (written above, in this same pass) is
                # already on screen instead of the whole rerun blocking on TTS
                # before the learner sees anything.
                audio = api_client.synthesize_speech(message["content"], "en")
                if audio:
                    st.audio(audio, autoplay=True)
                st.session_state["_last_played_audio_index"] = idx

    limit_reached = st.session_state.get("daily_limit_reached", False)

    if not st.session_state.messages and not limit_reached:
        _start_conversation(lesson)

    if not limit_reached:
        _handle_voice_input(lesson)
        components.html(AUTO_RECORD_JS, height=0)

    is_free_talk = st.session_state.mode == "free_talk"
    placeholder = (
        i18n.t("daily_limit_placeholder") if limit_reached else i18n.t("chat_input_placeholder")
    )

    def _render_text_input() -> None:
        if prompt := st.chat_input(placeholder, disabled=limit_reached):
            _handle_user_message(prompt, lesson, speak_reply=is_free_talk)

    # Free conversation is speech-first: keep the typed fallback tucked away
    # so voice stays the obvious default, only surfaced when the mic has issues.
    if is_free_talk and not limit_reached:
        with st.expander(i18n.t("text_fallback_label"), expanded=False):
            _render_text_input()
    else:
        _render_text_input()


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
        "needs_audio": True,
        **_message_metadata(lesson),
    }
    st.session_state.messages.append(assistant_message)
    st.rerun()


def _handle_voice_input(lesson: dict | None) -> None:
    st.markdown(VOICE_INPUT_DOCK_CSS, unsafe_allow_html=True)
    audio = st.audio_input(i18n.t("voice_input_label"), key="voice_input")
    if audio is None:
        return

    # st.audio_input keeps returning the same UploadedFile across reruns
    # until the learner re-records, unlike mic_recorder's just_once=True —
    # so track the last-processed file_id ourselves to avoid resending it.
    if audio.file_id == st.session_state.get("_last_voice_file_id"):
        return
    st.session_state["_last_voice_file_id"] = audio.file_id

    result = api_client.transcribe_audio(audio.getvalue(), mimetype=audio.type or "audio/wav")
    if result and result.get("text"):
        _handle_user_message(result["text"], lesson, speak_reply=True)


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
        "needs_audio": speak_reply,
        **_message_metadata(lesson),
    }
    st.session_state.messages.append(assistant_message)
    st.rerun()
