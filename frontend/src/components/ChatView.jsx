import { useEffect, useRef, useState } from "react";
import { chat, voice } from "../api/client";
import CorrectionCard from "./CorrectionCard.jsx";
import MicButton from "./MicButton.jsx";

export default function ChatView({ lang, t, lesson, mode, difficulty, onEndSession }) {
  const [messages, setMessages] = useState([]);
  const [mistakes, setMistakes] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [speakingIndex, setSpeakingIndex] = useState(null);
  const listRef = useRef(null);
  const audioRef = useRef(null);
  const micRef = useRef(null);
  const startedRef = useRef(false);

  const isFreeTalk = mode === "free_talk";

  async function handleSpeak(index, text, { autoArm = false } = {}) {
    if (!text) return;
    if (index !== null) setSpeakingIndex(index);

    // Stop active mic recording so it doesn't capture the AI speech output
    if (micRef.current && micRef.current.isRecording()) {
      micRef.current.stopRecording();
    }

    try {
      const blob = await voice.speak(text, lang === "ar" ? "ar" : "en");
      const url = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.src = url;
        await new Promise((resolve) => {
          const audio = audioRef.current;
          const cleanup = () => {
            audio.removeEventListener("ended", onEnded);
            audio.removeEventListener("error", onError);
          };
          const onEnded = () => {
            cleanup();
            resolve();
          };
          const onError = () => {
            cleanup();
            resolve();
          };
          audio.addEventListener("ended", onEnded);
          audio.addEventListener("error", onError);
          audio.play().catch((err) => {
            console.warn("Autoplay blocked or audio play error:", err);
            cleanup();
            resolve();
          });
        });
      }
    } catch (err) {
      console.warn("Speech synthesis error:", err);
    } finally {
      if (index !== null) setSpeakingIndex(null);
    }

    if (autoArm && isFreeTalk) {
      setTimeout(() => {
        if (micRef.current && !sending) {
          micRef.current.startRecording();
        }
      }, 300);
    }
  }

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    chat
      .start({ lesson_id: lesson ? lesson.id : null, difficulty, mode })
      .then((result) => {
        if (!result.reply) return;
        setMessages([{ role: "assistant", content: result.reply, corrections: result.corrections || [] }]);
        if (isFreeTalk) {
          handleSpeak(0, result.reply, { autoArm: true });
        }
      })
      .catch(() => {
        // Backend unreachable / daily limit — leave the chat empty; the
        // learner can still end the (empty) session from here.
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  async function sendText(text) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

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
      if (!result.reply) {
        setSending(false);
        return;
      }
      const corrections = result.corrections || [];
      if (corrections.length > 0) {
        setMistakes((prev) => [...prev, ...corrections]);
      }
      const replyIndex = nextMessages.length;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: result.reply, corrections },
      ]);
      if (isFreeTalk) {
        handleSpeak(replyIndex, result.reply, { autoArm: true });
      }
    } catch {
      // Leave the user message on screen; the send just failed silently
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    sendText(input);
  }

  function handleEnd() {
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
        <button type="button" className="btn" onClick={handleEnd}>
          {t("end_session_button")}
        </button>
      </div>

      <div className="message-list" ref={listRef}>
        {messages.map((msg, idx) => (
          <div key={idx}>
            <div className={`message-row ${msg.role}`}>
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
              </div>
            </div>
            {msg.corrections && msg.corrections.length > 0 && (
              <div className="message-row assistant">
                <div className="bubble-corrections">
                  {msg.corrections.map((feedback, fIdx) => (
                    <CorrectionCard key={fIdx} t={t} feedback={feedback} />
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <audio ref={audioRef} hidden />

      <form className="composer" onSubmit={handleSubmit}>
        <MicButton ref={micRef} t={t} disabled={sending} onTranscribed={(text) => sendText(text)} />
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("chat_input_placeholder")}
          disabled={sending}
        />
        <button type="submit" className="send-btn" disabled={sending || !input.trim()}>
          ➤
        </button>
      </form>
    </div>
  );
}

