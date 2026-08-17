// Speaks arabic_explanation aloud client-side via the browser's built-in
// speech synthesis. Mirrors the Streamlit app's behavior (components/correction_card.py):
// the backend's TTS voices don't cover Arabic, so this never round-trips to
// POST /api/v1/voice/speak for this text.
function speakArabic(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "ar-SA";
  window.speechSynthesis.speak(utterance);
}

export default function CorrectionCard({ t, feedback }) {
  const { wrong_text, correct_text, english_explanation, arabic_explanation, tip } = feedback;

  return (
    <div className="correction-card">
      <div className="correction-title">{t("correction_title")}</div>

      {wrong_text && (
        <div className="correction-line">
          {t("your_sentence_label")} {wrong_text}
        </div>
      )}

      {correct_text && (
        <div className="correction-line">
          {t("better_sentence_label")} {correct_text}
        </div>
      )}

      {arabic_explanation && (
        <>
          <div className="rtl-arabic-explanation" dir="rtl">
            {arabic_explanation}
          </div>
          <button type="button" className="listen-btn" onClick={() => speakArabic(arabic_explanation)}>
            {t("listen_button")}
          </button>
        </>
      )}

      {english_explanation && (
        <div className="correction-caption">{english_explanation}</div>
      )}

      {tip && (
        <div className="correction-tip">
          {t("tip_label")} {tip}
        </div>
      )}
    </div>
  );
}
