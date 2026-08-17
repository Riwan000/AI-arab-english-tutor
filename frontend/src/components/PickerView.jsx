import { useEffect, useState } from "react";
import { lessons as lessonsApi } from "../api/client";

const MODES = ["lesson", "free_talk"];
const DIFFICULTIES = ["beginner", "intermediate", "advanced"];

export default function PickerView({ lang, t, mode, difficulty, setMode, setDifficulty, onContinue }) {
  const [lessonList, setLessonList] = useState([]);
  const [selectedLessonId, setSelectedLessonId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (mode !== "lesson") return;
    setLoading(true);
    setError("");
    lessonsApi
      .list()
      .then((data) => setLessonList(data.lessons || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [mode]);

  function handleContinue() {
    if (mode === "lesson") {
      const lesson = lessonList.find((l) => l.id === selectedLessonId);
      if (!lesson) return;
      onContinue(lesson);
    } else {
      onContinue(null);
    }
  }

  const canContinue = mode === "free_talk" || Boolean(selectedLessonId);

  return (
    <div className="page">
      <div className="card card-wide">
        <h2>{t("mode_picker_header")}</h2>

        <div className="field">
          <label>{t("mode_field_label")}</label>
          <div className="option-group">
            {MODES.map((m) => (
              <button
                key={m}
                type="button"
                className={`option-pill ${mode === m ? "active" : ""}`}
                onClick={() => setMode(m)}
              >
                {t(m === "lesson" ? "mode_lesson" : "mode_free_talk")}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label>{t("difficulty_field_label")}</label>
          <div className="option-group">
            {DIFFICULTIES.map((d) => (
              <button
                key={d}
                type="button"
                className={`option-pill ${difficulty === d ? "active" : ""}`}
                onClick={() => setDifficulty(d)}
              >
                {t(`difficulty_${d}`)}
              </button>
            ))}
          </div>
        </div>

        {mode === "lesson" && (
          <div className="field">
            <label>{t("choose_lesson_label")}</label>
            {loading && <span className="muted">{t("loading")}</span>}
            {error && <div className="form-error">{error}</div>}
            {!loading && !error && lessonList.length === 0 && (
              <span className="muted">{t("no_lessons_available")}</span>
            )}
            <div className="lesson-list">
              {lessonList.map((lesson) => (
                <button
                  key={lesson.id}
                  type="button"
                  className={`lesson-list-item ${selectedLessonId === lesson.id ? "active" : ""}`}
                  onClick={() => setSelectedLessonId(lesson.id)}
                >
                  <span className="lesson-item-title">{lesson.title}</span>
                  <span className="lesson-item-desc">{lesson.description}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <button
          type="button"
          className="btn btn-primary"
          style={{ width: "100%", marginTop: "0.5rem" }}
          disabled={!canContinue}
          onClick={handleContinue}
        >
          {t("continue_button")}
        </button>
      </div>
    </div>
  );
}
