import { useEffect, useRef, useState } from "react";
import { ApiError, chat, usage, voice } from "../api/client";
import CorrectionCard from "./CorrectionCard.jsx";
import MicButton from "./MicButton.jsx";
import { playStreamedAudio } from "../lib/streamedAudio";

export default function ChatView({ lang, t, lesson, mode, difficulty, onEndSession }) {
  const [messages, setMessages] = useState([]);
  const [mistakes, setMistakes] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [speakingIndex, setSpeakingIndex] = useState(null);
  const [limitReached, setLimitReached] = useState(false);
  const [usageToday, setUsageToday] = useState(null);
  const [draft, setDraft] = useState(null);
  const [endingSession, setEndingSession] = useState(false);
  const listRef = useRef(null);
  const audioRef = useRef(null);
  const micRef = useRef(null);
  const startedRef = useRef(false);
  const speechAbortRef = useRef(null);

  function isMessageLimitError(err) {
    return err instanceof ApiError && err.status === 429 && err.detail?.kind !== "voice";
  }

  function refreshUsage() {
    usage
      .today()
      .then(({ messages_used, messages_limit }) =>
        setUsageToday({ used: messages_used, limit: messages_limit })
      )
      .catch(() => {
        // Usage caption is a nice-to-have — don't break the chat over it.
      });
  }

  async function handleSpeak(index, text, { autoArm = false } = {}) {
    if (!text) return;
    if (index !== null) setSpeakingIndex(index);

    // Stop active mic recording so it doesn't capture the AI speech output
    if (micRef.current && micRef.current.isRecording()) {
      micRef.current.stopRecording();
    }

    // Cancel any speech still streaming from a previous call before reusing
    // the shared <audio> element for this one.
    speechAbortRef.current?.abort();
    const controller = new AbortController();
    speechAbortRef.current = controller;

    try {
      const response = await voice.speak(text, lang === "ar" ? "ar" : "en");
      if (audioRef.current) {
        await playStreamedAudio(audioRef.current, response, { signal: controller.signal });
      }
    } catch (err) {
      console.warn("Speech synthesis error:", err);
    } finally {
      if (index !== null) setSpeakingIndex(null);
      if (speechAbortRef.current === controller) {
        speechAbortRef.current = null;
      }
    }

    if (autoArm) {
      setTimeout(() => {
        if (micRef.current && !sending) {
          micRef.current.startRecording();
        }
      }, 300);
    }
  }

  function startFreshConversation() {
    chat
      .start({ lesson_id: lesson ? lesson.id : null, difficulty, mode })
      .then((result) => {
        refreshUsage();
        if (!result.reply) return;
        setMessages([{ role: "assistant", content: result.reply, corrections: result.corrections || [] }]);
        handleSpeak(0, result.reply, { autoArm: true });
      })
      .catch((err) => {
        // Backend unreachable / daily limit — leave the chat empty; the
        // learner can still end the (empty) session from here.
        if (isMessageLimitError(err)) {
          setLimitReached(true);
        }
      });
  }

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    refreshUsage();

    // Drafts only ever exist for free-talk sessions — lesson mode always
    // starts fresh. If a draft is found, hold off starting a new
    // conversation until the learner picks resume vs. start fresh.
    if (mode === "free_talk") {
      chat
        .getDraft()
        .then((found) => {
          if (found) {
            setDraft(found);
          } else {
            startFreshConversation();
          }
        })
        .catch(() => startFreshConversation());
      return;
    }

    startFreshConversation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleResumeDraft() {
    setMessages(draft?.messages || []);
    setDraft(null);
  }

  function handleStartFresh() {
    setDraft(null);
    startFreshConversation();
  }

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  async function sendText(text) {
    const trimmed = text.trim();
    if (!trimmed || sending || endingSession) return;

    if (micRef.current && micRef.current.isRecording()) {
      micRef.current.stopRecording();
    }

    const nextMessages = [...messages, { role: "user", content: trimmed }];
    setMessages(nextMessages);
    setInput("");
    setSending(true);

    try {
      const result = await chat.message({
        lesson_id: lesson ? lesson.id : null,
        difficulty,
        mode,
        messages: nextMessages.map(({ role, content }) => ({ role, content })),
      });
      refreshUsage();
      if (!result.reply) {
        setSending(false);
        return;
      }
      const corrections = result.corrections || [];
      const updatedMistakes =
        corrections.length > 0 ? [...mistakes, ...corrections] : mistakes;
      if (corrections.length > 0) {
        setMistakes(updatedMistakes);
      }
      const replyIndex = nextMessages.length;
      const assistantMessage = { role: "assistant", content: result.reply, corrections };
      const finalMessages = [...nextMessages, assistantMessage];
      setMessages(finalMessages);

      if (result.session_ending) {
        // The model detected the learner is wrapping up — let the farewell
        // finish speaking before leaving for the summary screen, since
        // unmounting ChatView tears down the <audio> element and cuts the
        // reply off mid-sentence.
        setEndingSession(true);
        await handleSpeak(replyIndex, result.reply, { autoArm: false });
        onEndSession(finalMessages, updatedMistakes);
        return;
      }

      handleSpeak(replyIndex, result.reply, { autoArm: true });
    } catch (err) {
      // Leave the user message on screen; the send just failed silently —
      // unless it's the daily message-limit 429, which rolls the optimistic
      // message back (mirrors Streamlit's st.session_state.messages.pop()).
      if (isMessageLimitError(err)) {
        setMessages((prev) => prev.slice(0, -1));
        setLimitReached(true);
      }
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    sendText(input);
  }

  function handleEnd() {
    if (endingSession) return;
    if (micRef.current && micRef.current.isRecording()) {
      micRef.current.stopRecording();
    }
    onEndSession(messages, mistakes);
  }

  const title = lesson
    ? t("training_header_lesson", { title: lesson.title })
    : t("training_header_free_talk");

  return (
    <div className="chat-view">
      <div className="chat-view-header">
        <h2>{title}</h2>
        <button type="button" className="btn" onClick={handleEnd} disabled={endingSession}>
          {t("end_session_button")}
        </button>
      </div>

      {usageToday && (
        <span className="muted">
          {t("messages_today_caption", { used: usageToday.used, limit: usageToday.limit })}
        </span>
      )}

      {draft && (
        <div className="draft-resume-banner">
          <span>{t("resume_prompt_message")}</span>
          <div className="draft-resume-actions">
            <button type="button" className="btn btn-primary" onClick={handleResumeDraft}>
              {t("resume_button")}
            </button>
            <button type="button" className="btn btn-ghost" onClick={handleStartFresh}>
              {t("start_fresh_button")}
            </button>
          </div>
        </div>
      )}

      <div className="message-list" ref={listRef}>
        {messages.map((msg, idx) => (
          <div key={idx} className={`message-row ${msg.role}`}>
            <div className={`bubble ${msg.role}`}>
              {msg.content}
              {msg.role === "assistant" && (
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ marginInlineStart: "0.4rem", fontSize: "0.85rem" }}
                  onClick={() => handleSpeak(idx, msg.content, { autoArm: idx === messages.length - 1 })}
                  disabled={speakingIndex === idx}
                >
                  {speakingIndex === idx ? "🔊..." : "🔊"}
                </button>
              )}
              {msg.corrections && msg.corrections.length > 0 && (
                <div className="corrections-inline">
                  {msg.corrections.map((feedback, fIdx) => (
                    <CorrectionCard key={fIdx} t={t} feedback={feedback} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {endingSession && (
          <div className="message-row assistant">
            <span className="system-note">{t("session_ending_notice")}</span>
          </div>
        )}
      </div>

      <audio ref={audioRef} hidden />

      <form className="composer" onSubmit={handleSubmit}>
        <MicButton
          ref={micRef}
          t={t}
          disabled={sending || limitReached || endingSession}
          onTranscribed={(text) => sendText(text)}
        />
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={limitReached ? t("daily_limit_placeholder") : t("chat_input_placeholder")}
          disabled={sending || limitReached || endingSession}
        />
        <button
          type="submit"
          className="send-btn"
          disabled={sending || limitReached || endingSession || !input.trim()}
        >
          ➤
        </button>
      </form>
    </div>
  );
}
