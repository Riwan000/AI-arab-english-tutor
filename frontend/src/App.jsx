import { useEffect, useState, useCallback } from "react";
import { getStoredToken, storeToken, sessions } from "./api/client";
import { t as translate, DEFAULT_LANGUAGE } from "./i18n";
import LanguageToggle from "./components/LanguageToggle.jsx";
import AuthView from "./components/AuthView.jsx";
import PickerView from "./components/PickerView.jsx";
import LessonView from "./components/LessonView.jsx";
import ChatView from "./components/ChatView.jsx";
import SummaryView from "./components/SummaryView.jsx";
import SessionHistoryView from "./components/SessionHistoryView.jsx";

const USER_STORAGE_KEY = "englishTutor.user";
const LANG_STORAGE_KEY = "englishTutor.language";

// Central view-state switch, mirroring the Streamlit app's session-state flow:
// auth -> picker -> (lesson ->) chat -> summary
export default function App() {
  const [lang, setLang] = useState(
    () => localStorage.getItem(LANG_STORAGE_KEY) || DEFAULT_LANGUAGE
  );
  const [token, setToken] = useState(() => getStoredToken());
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem(USER_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  });

  const [view, setView] = useState(() => (getStoredToken() ? "picker" : "auth"));
  const [mode, setMode] = useState("lesson");
  const [difficulty, setDifficulty] = useState("beginner");
  const [selectedLesson, setSelectedLesson] = useState(null);
  const [sessionMessages, setSessionMessages] = useState([]);
  const [sessionMistakes, setSessionMistakes] = useState([]);
  const [summary, setSummary] = useState(null);

  const t = useCallback((key, params) => translate(lang, key, params), [lang]);
  const dir = lang === "ar" ? "rtl" : "ltr";

  useEffect(() => {
    localStorage.setItem(LANG_STORAGE_KEY, lang);
  }, [lang]);

  useEffect(() => {
    document.documentElement.dir = dir;
    document.documentElement.lang = lang;
  }, [dir, lang]);

  useEffect(() => {
    function handleUnauthorized() {
      handleLogout();
    }
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("auth:unauthorized", handleUnauthorized);
  }, []);

  function handleAuthSuccess(newToken, newUser) {
    storeToken(newToken);
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
    setView("picker");
  }

  function handleLogout() {
    storeToken(null);
    localStorage.removeItem(USER_STORAGE_KEY);
    setToken(null);
    setUser(null);
    setView("auth");
  }

  function handlePickerContinue(lesson) {
    setSelectedLesson(lesson);
    setSessionMessages([]);
    setSessionMistakes([]);
    setSummary(null);
    setView(mode === "lesson" ? "lesson" : "chat");
  }

  function handleStartFromLesson() {
    setView("chat");
  }

  async function handleEndSession(messages, mistakes) {
    setSessionMessages(messages);
    setSessionMistakes(mistakes);
    try {
      const result = await sessions.create({
        lesson_id: selectedLesson ? selectedLesson.id : null,
        messages: messages.map(({ role, content }) => ({ role, content })),
        mistakes,
        mode,
      });
      setSummary(result);
    } catch (err) {
      setSummary({ error: err.message });
    }
    setView("summary");
  }

  function handleNewSession() {
    setSelectedLesson(null);
    setSessionMessages([]);
    setSessionMistakes([]);
    setSummary(null);
    setView("picker");
  }

  return (
    <div className="app-shell" dir={dir}>
      <header className="app-header">
        <h1>{t("app_title")}</h1>
        <div className="header-actions">
          {token && (view === "picker" || view === "summary") && (
            <button className="btn btn-ghost" onClick={() => setView("history")}>
              {t("past_sessions_button")}
            </button>
          )}
          {user && (
            <button className="btn btn-ghost" onClick={handleLogout}>
              {t("logout_button")}
            </button>
          )}
          <LanguageToggle lang={lang} setLang={setLang} />
        </div>
      </header>

      {view === "auth" && <AuthView lang={lang} t={t} onAuthSuccess={handleAuthSuccess} />}

      {view === "picker" && token && (
        <PickerView
          lang={lang}
          t={t}
          mode={mode}
          difficulty={difficulty}
          setMode={setMode}
          setDifficulty={setDifficulty}
          onContinue={handlePickerContinue}
        />
      )}

      {view === "lesson" && selectedLesson && (
        <LessonView
          lang={lang}
          t={t}
          lesson={selectedLesson}
          onStart={handleStartFromLesson}
          onBack={() => setView("picker")}
        />
      )}

      {view === "chat" && token && (
        <ChatView
          lang={lang}
          t={t}
          lesson={selectedLesson}
          mode={mode}
          difficulty={difficulty}
          onEndSession={handleEndSession}
        />
      )}

      {view === "summary" && (
        <SummaryView
          lang={lang}
          t={t}
          summary={summary}
          lesson={selectedLesson}
          messages={sessionMessages}
          mistakes={sessionMistakes}
          onNewSession={handleNewSession}
        />
      )}

      {view === "history" && (
        <SessionHistoryView t={t} onBack={() => setView("picker")} />
      )}
    </div>
  );
}
