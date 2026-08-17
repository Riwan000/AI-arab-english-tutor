import { useState } from "react";
import { auth } from "../api/client";

export default function AuthView({ t, onAuthSuccess }) {
  const [tab, setTab] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const result =
        tab === "login"
          ? await auth.login(email, password)
          : await auth.signup(email, password, displayName);
      onAuthSuccess(result.access_token, result.user);
    } catch (err) {
      setError(err.message || t("auth_error_fallback"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page">
      <div className="card">
        <div className="tabs">
          <button
            type="button"
            className={tab === "login" ? "active" : ""}
            onClick={() => setTab("login")}
          >
            {t("tab_login")}
          </button>
          <button
            type="button"
            className={tab === "signup" ? "active" : ""}
            onClick={() => setTab("signup")}
          >
            {t("tab_signup")}
          </button>
        </div>

        {error && <div className="form-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          {tab === "signup" && (
            <div className="field">
              <label htmlFor="display_name">{t("display_name_label")}</label>
              <input
                id="display_name"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
              />
            </div>
          )}

          <div className="field">
            <label htmlFor="email">{t("email_label")}</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label htmlFor="password">{t("password_label")}</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
            {tab === "signup" && <span className="field-hint">{t("password_help")}</span>}
          </div>

          <button type="submit" className="btn btn-primary" style={{ width: "100%" }} disabled={submitting}>
            {tab === "login" ? t("login_button") : t("signup_button")}
          </button>
        </form>
      </div>
    </div>
  );
}
