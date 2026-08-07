"""Session scoring: grammar score, vocabulary, recommendations."""

from collections import Counter


def calculate_session_summary(
    messages: list[dict],
    mistakes: list,
    lesson_title: str | None = None,
) -> dict:
    user_messages = [m for m in messages if m["role"] == "user"]
    exchanges = len(user_messages)
    mistake_count = len(mistakes)

    grammar_score = max(0, 100 - (mistake_count * 10)) if exchanges else 0

    mistake_types = list(dict.fromkeys(
        m.get("mistake_type") if isinstance(m, dict) else m.mistake_type
        for m in mistakes
    ))

    vocabulary = _extract_vocabulary(user_messages)

    title = lesson_title or "this lesson"
    recommendation = None
    if grammar_score < 70:
        recommendation = f"Practice {title} again tomorrow."
    elif grammar_score >= 90:
        recommendation = "Excellent work! Try a harder lesson next."

    return {
        "grammar": grammar_score,
        "exchanges": exchanges,
        "mistake_count": mistake_count,
        "mistake_types": mistake_types,
        "vocabulary": vocabulary,
        "recommendation": recommendation,
    }


def _extract_vocabulary(messages: list[dict]) -> list[str]:
    words: Counter = Counter()
    stop_words = {"i", "a", "the", "is", "am", "are", "do", "does", "my", "in", "at", "to", "and"}

    for msg in messages:
        for word in msg["content"].lower().split():
            cleaned = word.strip(".,!?")
            if cleaned and cleaned not in stop_words and len(cleaned) > 2:
                words[cleaned] += 1

    return [w.capitalize() for w, _ in words.most_common(8)]
