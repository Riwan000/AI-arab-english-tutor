import { useEffect, useState } from "react";
import { lessons as lessonsApi } from "../api/client";

export default function LessonView({ t, lesson, onStart, onBack }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    lessonsApi
      .get(lesson.id)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [lesson.id]);

  return (
    <div className="page">
      <div className="card card-wide">
        <h2>{lesson.title}</h2>
        <p className="muted">{lesson.description}</p>

        {error && <div className="form-error">{error}</div>}

        {detail && (
          <>
            {detail.examples?.length > 0 && (
              <div className="lesson-block">
                <h3>{t("examples_header")}</h3>
                {detail.examples.map((example, idx) => (
                  <code key={idx} className="example-block">
                    {example}
                  </code>
                ))}
              </div>
            )}

            {detail.negative_form?.length > 0 && (
              <div className="lesson-block">
                <h3>{t("negative_form_header")}</h3>
                <ul>
                  {detail.negative_form.map((line, idx) => (
                    <li key={idx}>{line}</li>
                  ))}
                </ul>
              </div>
            )}

            {detail.question_form?.length > 0 && (
              <div className="lesson-block">
                <h3>{t("question_form_header")}</h3>
                <ul>
                  {detail.question_form.map((line, idx) => (
                    <li key={idx}>{line}</li>
                  ))}
                </ul>
              </div>
            )}

            {detail.tips?.length > 0 && (
              <div className="lesson-block">
                <h3>{t("tips_header")}</h3>
                <ul>
                  {detail.tips.map((tip, idx) => (
                    <li key={idx}>{tip}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}

        <div style={{ display: "flex", gap: "0.6rem", marginTop: "1rem" }}>
          <button type="button" className="btn" onClick={onBack}>
            {t("back_button")}
          </button>
          <button type="button" className="btn btn-primary" style={{ flex: 1 }} onClick={onStart}>
            {t("start_training_button")}
          </button>
        </div>
      </div>
    </div>
  );
}
