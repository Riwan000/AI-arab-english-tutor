import { LANGUAGE_NAMES } from "../i18n";

export default function LanguageToggle({ lang, setLang }) {
  return (
    <div className="lang-toggle">
      {Object.entries(LANGUAGE_NAMES).map(([code, name]) => (
        <button
          key={code}
          type="button"
          className={code === lang ? "active" : ""}
          onClick={() => setLang(code)}
        >
          {name}
        </button>
      ))}
    </div>
  );
}
