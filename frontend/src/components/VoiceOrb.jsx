export default function VoiceOrb({ size = "hero", active, disabled, onClick, label }) {
  return (
    <button
      type="button"
      className={`orb-container ${size === "compact" ? "orb-compact" : ""} ${active ? "orb-active" : ""}`}
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
    >
      <div className="orb">
        <div className="orb-inner" />
        <div className="orb-inner" />
      </div>
    </button>
  );
}
