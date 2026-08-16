"""Application UI language (Arabic/English) — labels, headers, buttons, warnings.

Not for tutoring content: lesson text, `arabic_explanation`, `english_explanation`,
and LLM chat replies stay as returned by the backend regardless of this setting.
"""

import streamlit as st

DEFAULT_LANGUAGE = "ar"
LANGUAGE_NAMES = {"ar": "العربية", "en": "English"}

_STRINGS = {
    "ar": {
        "backend_unreachable": (
            "تعذّر الوصول إلى واجهة البرمجة الخلفية. شغّل uvicorn "
            "(uvicorn api.main:app --reload --port 8000) وتحقق من BACKEND_URL "
            "في .streamlit/secrets.toml."
        ),
        "app_title": "📚 معلم اللغة الإنجليزية",
        "tab_login": "تسجيل الدخول",
        "tab_signup": "إنشاء حساب",
        "email_label": "البريد الإلكتروني",
        "password_label": "كلمة المرور",
        "display_name_label": "الاسم المعروض",
        "login_button": "تسجيل الدخول",
        "signup_button": "إنشاء حساب",
        "password_help": "8 أحرف على الأقل.",
        "login_validation_error": "الرجاء إدخال البريد الإلكتروني وكلمة المرور.",
        "signup_validation_error": "الرجاء تعبئة جميع الحقول.",
        "mode_picker_header": "كيف تريد أن تتدرّب؟",
        "mode_field_label": "الوضع",
        "difficulty_field_label": "المستوى",
        "continue_button": "متابعة",
        "mode_difficulty_caption": "الوضع: {mode} · المستوى: {difficulty}",
        "no_lessons_available": "لا توجد دروس متاحة. تحقق من الاتصال بالخادم.",
        "choose_lesson_label": "اختر درسًا",
        "progress_header": "التقدم",
        "grammar_score_label": "درجة القواعد",
        "messages_today_caption": "الرسائل اليوم: {used}/{limit}",
        "common_mistakes_label": "الأخطاء الشائعة",
        "unknown_mistake": "غير معروف",
        "vocabulary_label": "المفردات",
        "end_session_button": "إنهاء الجلسة",
        "past_sessions_header": "الجلسات السابقة",
        "no_past_sessions": "لا توجد جلسات سابقة بعد.",
        "exchanges_label": "**التبادلات:**",
        "mistakes_colon_label": "**الأخطاء:**",
        "vocabulary_colon_label": "**المفردات:**",
        "mistake_types_label": "**أنواع الأخطاء:**",
        "exchanges_metric_label": "التبادلات",
        "mistakes_metric_label": "الأخطاء",
        "choose_lesson_warning": "الرجاء اختيار درس من الشريط الجانبي.",
        "training_header_lesson": "تدريب: {title}",
        "training_header_free_talk": "تدريب: محادثة حرة",
        "chat_input_placeholder": "اكتب إجابتك بالإنجليزية...",
        "daily_limit_placeholder": "تم الوصول إلى الحد اليومي للرسائل",
        "voice_input_label": "🎙️ تحدث",
        "lesson_load_error": "تعذر تحميل تفاصيل الدرس.",
        "examples_header": "أمثلة",
        "negative_form_header": "النفي",
        "question_form_header": "السؤال",
        "tips_header": "نصائح",
        "start_training_button": "ابدأ التدريب",
        "session_summary_header": "ملخص الجلسة",
        "session_saved_caption": "تم حفظ الجلسة (#{id})",
        "session_save_failed_caption": "تعذر حفظ الجلسة على الخادم.",
        "no_vocabulary_tracked": "لم يتم تتبع أي مفردات بعد.",
        "no_mistakes": "لا توجد أخطاء — عمل رائع!",
        "recommendation_header": "التوصية",
        "recommendation_default": "مارس {lesson} مرة أخرى غدًا.",
        "excellent_recommendation": "عمل ممتاز! جرّب درسًا أصعب في المرة القادمة.",
        "this_lesson_fallback": "هذا الدرس",
        "new_session_button": "بدء جلسة جديدة",
        "correction_title": "تقريبًا! تغيير بسيط واحد فقط.",
        "your_sentence_label": "❌ **جملتك:**",
        "better_sentence_label": "✅ **الجملة الأفضل:**",
        "listen_button": "🔊 استمع",
        "tip_label": "💡 نصيحة:",
    },
    "en": {
        "backend_unreachable": (
            "Couldn't reach the backend API. Start uvicorn "
            "(uvicorn api.main:app --reload --port 8000) and check BACKEND_URL "
            "in .streamlit/secrets.toml."
        ),
        "app_title": "📚 English Tutor",
        "tab_login": "Log in",
        "tab_signup": "Sign up",
        "email_label": "Email",
        "password_label": "Password",
        "display_name_label": "Display name",
        "login_button": "Log in",
        "signup_button": "Sign up",
        "password_help": "At least 8 characters.",
        "login_validation_error": "Please enter your email and password.",
        "signup_validation_error": "Please fill in all fields.",
        "mode_picker_header": "How do you want to practice?",
        "mode_field_label": "Mode",
        "difficulty_field_label": "Level",
        "continue_button": "Continue",
        "mode_difficulty_caption": "Mode: {mode} · Level: {difficulty}",
        "no_lessons_available": "No lessons available. Check your connection to the server.",
        "choose_lesson_label": "Choose a lesson",
        "progress_header": "Progress",
        "grammar_score_label": "Grammar score",
        "messages_today_caption": "Messages today: {used}/{limit}",
        "common_mistakes_label": "Common mistakes",
        "unknown_mistake": "Unknown",
        "vocabulary_label": "Vocabulary",
        "end_session_button": "End session",
        "past_sessions_header": "Past sessions",
        "no_past_sessions": "No past sessions yet.",
        "exchanges_label": "**Exchanges:**",
        "mistakes_colon_label": "**Mistakes:**",
        "vocabulary_colon_label": "**Vocabulary:**",
        "mistake_types_label": "**Mistake types:**",
        "exchanges_metric_label": "Exchanges",
        "mistakes_metric_label": "Mistakes",
        "choose_lesson_warning": "Please choose a lesson from the sidebar.",
        "training_header_lesson": "Practice: {title}",
        "training_header_free_talk": "Practice: Free Talk",
        "chat_input_placeholder": "Type your answer in English...",
        "daily_limit_placeholder": "Daily message limit reached",
        "voice_input_label": "🎙️ Speak",
        "lesson_load_error": "Couldn't load lesson details.",
        "examples_header": "Examples",
        "negative_form_header": "Negative form",
        "question_form_header": "Question form",
        "tips_header": "Tips",
        "start_training_button": "Start practicing",
        "session_summary_header": "Session summary",
        "session_saved_caption": "Session saved (#{id})",
        "session_save_failed_caption": "Couldn't save the session to the server.",
        "no_vocabulary_tracked": "No vocabulary tracked yet.",
        "no_mistakes": "No mistakes — great job!",
        "recommendation_header": "Recommendation",
        "recommendation_default": "Practice {lesson} again tomorrow.",
        "excellent_recommendation": "Excellent work! Try a harder lesson next time.",
        "this_lesson_fallback": "this lesson",
        "new_session_button": "Start a new session",
        "correction_title": "Almost! Just one small change.",
        "your_sentence_label": "❌ **Your sentence:**",
        "better_sentence_label": "✅ **Better sentence:**",
        "listen_button": "🔊 Listen",
        "tip_label": "💡 Tip:",
    },
}

MODE_LABELS = {
    "ar": {"lesson": "درس", "free_talk": "محادثة حرة"},
    "en": {"lesson": "Lesson", "free_talk": "Free Talk"},
}
DIFFICULTY_LABELS = {
    "ar": {"beginner": "مبتدئ", "intermediate": "متوسط", "advanced": "متقدم"},
    "en": {"beginner": "Beginner", "intermediate": "Intermediate", "advanced": "Advanced"},
}


def current_language() -> str:
    return st.session_state.get("app_language", DEFAULT_LANGUAGE)


def is_rtl() -> bool:
    return current_language() == "ar"


def t(key: str, **kwargs) -> str:
    template = _STRINGS.get(current_language(), _STRINGS[DEFAULT_LANGUAGE]).get(key, key)
    return template.format(**kwargs) if kwargs else template


def mode_label(mode: str) -> str:
    labels = MODE_LABELS.get(current_language(), MODE_LABELS[DEFAULT_LANGUAGE])
    return labels.get(mode, mode)


def difficulty_label(difficulty: str) -> str:
    labels = DIFFICULTY_LABELS.get(current_language(), DIFFICULTY_LABELS[DEFAULT_LANGUAGE])
    return labels.get(difficulty, difficulty)


def rtl_style(selector: str) -> str:
    direction = "rtl" if is_rtl() else "ltr"
    text_align = "right" if is_rtl() else "left"
    return f"<style>{selector} {{ direction: {direction}; text-align: {text_align}; }}</style>"


def render_language_switcher(cookie_manager, *, key: str) -> None:
    options = list(LANGUAGE_NAMES.keys())
    current = current_language()
    index = options.index(current) if current in options else options.index(DEFAULT_LANGUAGE)
    selected = st.selectbox(
        "🌐",
        options=options,
        index=index,
        format_func=lambda code: LANGUAGE_NAMES[code],
        key=key,
        label_visibility="collapsed",
    )
    if selected != current:
        st.session_state.app_language = selected
        cookie_manager.set("app_language", selected)
        st.rerun()
