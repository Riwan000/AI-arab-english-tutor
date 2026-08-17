export default function SummaryView({ t, summary, onNewSession }) {
  const failed = !summary || summary.error;

  return (
    <div className="page">
      <div className="card card-wide">
        <h2>{t("session_summary_header")}</h2>

        {failed && <div className="form-error">{t("session_save_failed_caption")}</div>}

        {!failed && (
          <>
            <div className="summary-metrics">
              <div className="metric">
                <div className="metric-value">{summary.grammar_score}</div>
                <div className="metric-label">{t("grammar_score_label")}</div>
              </div>
              <div className="metric">
                <div className="metric-value">{summary.exchange_count}</div>
                <div className="metric-label">{t("exchanges_metric_label")}</div>
              </div>
              <div className="metric">
                <div className="metric-value">{summary.mistake_count}</div>
                <div className="metric-label">{t("mistakes_metric_label")}</div>
              </div>
            </div>

            <div className="lesson-block">
              <h3>{t("vocabulary_label")}</h3>
              {summary.vocabulary && summary.vocabulary.length > 0 ? (
                <div className="tag-list">
                  {summary.vocabulary.map((word, idx) => (
                    <span key={idx} className="tag">
                      {word}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="muted">{t("no_vocabulary_tracked")}</span>
              )}
            </div>

            {summary.mistake_types && summary.mistake_types.length > 0 && (
              <div className="lesson-block">
                <h3>{t("mistake_types_label")}</h3>
                <div className="tag-list">
                  {summary.mistake_types.map((type, idx) => (
                    <span key={idx} className="tag">
                      {type}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {summary.recommendation && (
              <div className="lesson-block">
                <h3>{t("recommendation_header")}</h3>
                <p>{summary.recommendation}</p>
              </div>
            )}
          </>
        )}

        <button
          type="button"
          className="btn btn-primary"
          style={{ width: "100%", marginTop: "1rem" }}
          onClick={onNewSession}
        >
          {t("new_session_button")}
        </button>
      </div>
    </div>
  );
}
