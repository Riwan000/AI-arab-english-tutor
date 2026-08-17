export default function CorrectionCard({ t, feedback }) {
  const { wrong_text, correct_text, english_explanation, arabic_explanation, tip } = feedback;

  return (
    <div className="correction-text">
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
        <div className="rtl-arabic-explanation" dir="rtl">
          {arabic_explanation}
        </div>
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
