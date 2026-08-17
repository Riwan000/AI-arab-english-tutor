"""Phase 8 exit verification — issues #145-#146.

Phase 8 is pure Streamlit-chrome localization + scoped CSS, with no backend
route surface — so unlike the phase 6/7 exit suites, these are static-analysis
checks over the component source rather than HTTP-level tests. They encode the
two written exit criteria from docs/VOICE_AGENT_TASK_BREAKDOWN.md (8.7-8.8):
every non-practice-content string reads in Arabic, and the scoped RTL CSS
never leaks into the mixed-content areas (chat bubbles, lesson examples) that
must stay LTR.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Display calls whose first positional argument is learner-facing chrome.
CHROME_CALLS = {
    "header", "title", "subheader", "button", "radio", "selectbox", "caption",
    "warning", "info", "error", "write", "markdown", "text_input", "chat_input",
    "metric", "expander", "form_submit_button", "success",
}
ENGLISH_WORD_RE = re.compile(r"[A-Za-z]{3,}")
MARKUP_RE = re.compile(r"[<>]")

# Latin technical tokens that legitimately appear inside otherwise-Arabic
# chrome (app.py's dev-facing backend-unreachable warning names the real
# command/env-var/path a developer needs). Stripped out before the English-word
# check runs, so — unlike a blanket "string contains some Arabic somewhere"
# exemption — one legitimate technical term can never mask an untranslated
# English sentence smuggled in elsewhere in the same literal.
KNOWN_TECHNICAL_TERMS = (
    "uvicorn",
    "api.main:app",
    "--reload",
    "--port",
    "BACKEND_URL",
    ".streamlit/secrets.toml",
)


def _strip_known_technical_terms(text: str) -> str:
    for term in KNOWN_TECHNICAL_TERMS:
        text = text.replace(term, "")
    return text


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _static_text(node: ast.expr) -> str:
    """Concatenate the literal string content of a call argument.

    Handles plain literals, adjacent-literal concatenation ("a" "b" across
    lines — ast folds this into one Constant automatically), and f-strings by
    joining only their static Constant segments and skipping interpolated
    ``{expr}`` parts. Non-string arguments (e.g. `lesson["title"]`) yield "".
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            value.value
            for value in node.values
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        )
    return ""


def _chrome_literals(relative_path: str) -> list[tuple[int, str, str]]:
    """Every `st.<chrome_call>(...)`'s first-argument literal text, with its line number."""
    tree = ast.parse(_read(relative_path), filename=relative_path)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr in CHROME_CALLS
            and isinstance(func.value, ast.Name)
            and func.value.id == "st"
        ):
            continue
        text = _static_text(node.args[0])
        if text:
            found.append((node.lineno, func.attr, text))
    return found

# RTL CSS must target a specific class/selector, never the whole page.
GLOBAL_SELECTOR_RE = re.compile(r"<style>\s*(\*|body|html|\.stApp)\s*\{[^}]*direction:\s*rtl")
DIRECTION_RTL_RE = re.compile(r"direction:\s*rtl")
DIR_ATTR_RTL_RE = re.compile(r"""dir\s*=\s*["']rtl["']""")
UNSCOPED_SELECTORS = {"*", "body", "html", ".stApp"}
# Since #157's i18n system, RTL is computed at render time via
# i18n.rtl_style(selector) instead of a module-level CSS-string constant
# (module constants can't react to the app_language session-state toggle).
# Two alternatives (not a shared [\'"] class) so a selector containing the
# other quote character — e.g. sidebar.py's '[data-testid="stSidebar"]' —
# isn't truncated at its first embedded quote.
RTL_STYLE_CALL_RE = re.compile(r"""i18n\.rtl_style\(\s*(?:'([^']*)'|"([^"]*)")""")

# Pure-chrome screens: pre-existing scoped RTL from 8.6, plus auth/mode-picker
# chrome completed as part of the #145/#146 sweep (see components/auth_view.py,
# components/mode_picker.py).
#
# components/correction_card.py is deliberately absent: its listen button and
# the RTL styling that only ever existed to support that button's Arabic
# explanation block were both removed together (the card now renders plain
# markdown), so it no longer carries any RTL CSS of its own. RTL support is
# unaffected everywhere else -- it remains scoped to the files below.
RTL_SCOPED_FILES = (
    "components/sidebar.py",
    "components/summary.py",
    "components/auth_view.py",
    "components/mode_picker.py",
)

# Mixed-content areas (English chat bubbles / lesson examples) or app-wide
# entry point — must never carry RTL, per docs/VOICE_AGENT_IMPLEMENTATION_PLAN.md §F.
MUST_STAY_LTR_FILES = (
    "components/chat.py",
    "components/lesson_view.py",
    "app.py",
)

ALL_CHROME_FILES = MUST_STAY_LTR_FILES + RTL_SCOPED_FILES


# --- #145/#146: every non-practice-content string reads in Arabic ----------


def test_no_hardcoded_english_chrome_strings_remain():
    """Issue #146 — full sweep: no leftover English literal in a chrome display call.

    Regression guard for the exact gap #146's walkthrough found: 8.5 had been
    marked done, but components/mode_picker.py, auth_view.py, lesson_view.py
    and app.py's backend-unreachable warning still had hardcoded English
    chrome. Lesson content itself (lesson["title"], examples, tips) is read
    from variables, not literals, so it never appears in _chrome_literals().

    AST-based (not regex-over-raw-text) specifically because Python folds
    adjacent string-literal concatenation ("a" "b" across lines, as app.py's
    multi-line warning uses) into one Constant — a regex anchored on the first
    quoted literal would miss English smuggled into a later fragment.
    """
    offenders = []
    for relative_path in ALL_CHROME_FILES:
        for lineno, call_name, text in _chrome_literals(relative_path):
            # Raw HTML/CSS literals (<style>/<div> injected via
            # unsafe_allow_html) aren't chrome prose — skip them outright.
            if MARKUP_RE.search(text):
                continue
            remainder = _strip_known_technical_terms(text)
            if ENGLISH_WORD_RE.search(remainder):
                offenders.append(f"{relative_path}:{lineno} st.{call_name}({text!r})")

    assert not offenders, "Hardcoded English chrome strings found:\n" + "\n".join(offenders)


# --- #145: RTL/LTR boundaries -----------------------------------------------


def test_rtl_css_is_present_and_scoped_in_arabic_chrome_screens():
    """Issue #145 — the pure-Arabic-chrome screens carry scoped RTL CSS.

    RTL support comes either as a literal `direction: rtl` CSS string or as a
    call to `i18n.rtl_style(selector)` (the app-language-aware screens) —
    either way it must target a specific selector, never the whole page.

    The per-selector checks below run against `i18n.rtl_style()`'s actual
    return value, not just the selector text parsed out of the caller's
    source — a static-source-only check would pass even if `rtl_style()`
    itself started ignoring its argument and hardcoding an unscoped
    selector, since the caller-side literal would still look fine.
    """
    import i18n as i18n_module

    for relative_path in RTL_SCOPED_FILES:
        source = _read(relative_path)
        dynamic_calls = [g1 or g2 for g1, g2 in RTL_STYLE_CALL_RE.findall(source)]
        assert DIRECTION_RTL_RE.search(source) or dynamic_calls, (
            f"{relative_path} is missing RTL CSS"
        )
        assert not GLOBAL_SELECTOR_RE.search(source), (
            f"{relative_path} applies RTL with an unscoped selector "
            "(*, body, html, .stApp) instead of a targeted container class"
        )
        for selector in dynamic_calls:
            assert selector.strip() not in UNSCOPED_SELECTORS, (
                f"{relative_path} applies RTL with an unscoped selector "
                f"({selector}) instead of a targeted container class"
            )
            rendered = i18n_module.rtl_style(selector)
            assert selector in rendered, (
                f"{relative_path}: i18n.rtl_style({selector!r}) did not honor "
                f"its selector argument — got {rendered!r}"
            )
            assert not GLOBAL_SELECTOR_RE.search(rendered), (
                f"{relative_path}: i18n.rtl_style({selector!r}) rendered an "
                f"unscoped selector — got {rendered!r}"
            )


def test_mixed_content_screens_stay_ltr():
    """Issue #145 — chat bubbles, lesson examples, and app.py never flip to RTL.

    These screens mix Arabic chrome with English practice content (chat
    replies, lesson examples/tips); per docs/VOICE_AGENT_IMPLEMENTATION_PLAN.md
    §F a blanket RTL here would also break the phase-9 mic/voice controls.
    """
    for relative_path in MUST_STAY_LTR_FILES:
        source = _read(relative_path)
        assert not DIRECTION_RTL_RE.search(source), f"{relative_path} must stay LTR"
        assert not DIR_ATTR_RTL_RE.search(source), f"{relative_path} must stay LTR"


def test_rtl_scoping_is_not_applied_app_wide():
    """Issue #145 — app.py itself injects no global RTL style; each screen scopes its own."""
    app_source = _read("app.py")
    assert "direction" not in app_source
    assert "unsafe_allow_html" not in app_source


def main() -> int:
    test_no_hardcoded_english_chrome_strings_remain()
    print("No hardcoded English chrome strings remain in learner-facing screens (#146) — OK")

    test_rtl_css_is_present_and_scoped_in_arabic_chrome_screens()
    print("RTL CSS present and scoped (not global) in all Arabic-chrome screens (#145) — OK")

    test_mixed_content_screens_stay_ltr()
    print("Chat, lesson view, and app.py stay LTR (#145) — OK")

    test_rtl_scoping_is_not_applied_app_wide()
    print("No app-wide RTL injection in app.py (#145) — OK")

    print("Phase 8 exit checklist (issues #145-#146):")
    print("  [x] Sidebar, summary, correction card, auth, and mode-picker chrome is Arabic")
    print("  [x] RTL CSS is scoped to each screen's own container, never applied app-wide")
    print("  [x] Chat bubbles, lesson examples/tips, and app.py's warning stay LTR")
    print("  [ ] Manual: streamlit run app.py, visually confirm Arabic text renders")
    print("      right-to-left and right-aligned in the sidebar/summary/auth/mode-picker")
    print("      screens, and that chat bubbles + English lesson content")
    print("      still read left-to-right (docs §I frontend bullet)")
    print("Phase 8 exit verification (issues #145-#146): OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
