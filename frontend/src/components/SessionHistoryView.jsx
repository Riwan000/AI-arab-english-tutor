import { useEffect, useState } from "react";
import { sessions } from "../api/client";

export default function SessionHistoryView({ t, onBack }) {
  const [sessionList, setSessionList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [details, setDetails] = useState({});

  useEffect(() => {
    sessions
      .list(10)
      .then((data) => setSessionList(data || []))
      .catch(() => setSessionList([]))
      .finally(() => setLoading(false));
  }, []);

  function toggleExpanded(id) {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (!details[id]) {
      sessions
        .get(id)
        .then((detail) => setDetails((prev) => ({ ...prev, [id]: detail })))
        .catch(() => {});
    }
  }

  return (
    <div className="page">
      <div className="card card-wide">
        <button type="button" className="btn btn-ghost" onClick={onBack}>
          {t("back_button")}
        </button>
        <h2>{t("past_sessions_header")}</h2>

        {loading && <span className="muted">{t("loading")}</span>}

        {!loading && sessionList.length === 0 && (
          <span className="muted">{t("no_past_sessions")}</span>
        )}

        {!loading && sessionList.length > 0 && (
          <div className="lesson-list">
            {sessionList.map((session) => {
              const isExpanded = expandedId === session.id;
              const detail = details[session.id];
              return (
                <div key={session.id}>
                  <button
                    type="button"
                    className={`lesson-list-item ${isExpanded ? "active" : ""}`}
                    onClick={() => toggleExpanded(session.id)}
                  >
                    <span className="lesson-item-title">{session.lesson_title}</span>
                    <span className="lesson-item-desc">
                      {session.grammar_score} · {new Date(session.ended_at).toLocaleString()}
                    </span>
                  </button>

                  {isExpanded && (
                    <div className="lesson-block">
                      {!detail && <span className="muted">{t("loading")}</span>}
                      {detail && (
                        <>
                          <p>
                            {t("exchanges_label")} {detail.exchange_count}
                          </p>
                          <p>
                            {t("mistakes_colon_label")} {detail.mistake_count}
                          </p>
                          {detail.vocabulary && detail.vocabulary.length > 0 && (
                            <p>
                              {t("vocabulary_colon_label")} {detail.vocabulary.join(", ")}
                            </p>
                          )}
                          {detail.mistake_types && detail.mistake_types.length > 0 && (
                            <div>
                              <h3>{t("mistake_types_label")}</h3>
                              <div className="tag-list">
                                {detail.mistake_types.map((mt, idx) => (
                                  <span key={idx} className="tag">
                                    {mt.mistake_type} ({mt.count})
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                          {detail.recommendation && (
                            <div className="lesson-block">
                              <h3>{t("recommendation_header")}</h3>
                              <p>{detail.recommendation}</p>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
