"""Global stylesheet: fonts + the visual bits config.toml can't reach.

Colors, base font, heading font, border color and radii are set in
.streamlit/config.toml so native widgets (buttons, inputs, sliders, chat
input) pick them up automatically. This module only covers what the theme
API doesn't: loading the actual font files, and app-specific chrome like
chat bubbles, the auth card and the mic/send buttons.
"""

import streamlit as st

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Cairo:wght@400;600;700&display=swap');

/* ---- auth card (login / signup) ---- */
.st-key-auth-rtl {
    max-width: 26rem;
    margin: 3rem auto 0;
    padding: 2rem 2rem 1.5rem;
    background: #FFFFFF;
    border: 1px solid #F3D9BE;
    border-radius: 1.25rem;
    box-shadow: 0 16px 40px -24px rgba(28, 25, 23, 0.35);
}
.st-key-auth-rtl [data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 0.25rem;
    background: #FDF0E4;
    padding: 0.25rem;
    border-radius: 0.7rem;
}
.st-key-auth-rtl [data-baseweb="tab"] {
    border-radius: 0.55rem;
}
.st-key-auth-rtl [data-baseweb="tab-highlight"],
.st-key-auth-rtl [data-baseweb="tab-border"] {
    display: none;
}
.st-key-auth-rtl [aria-selected="true"] {
    background: #FFFFFF;
    box-shadow: 0 1px 2px rgba(28, 25, 23, 0.08);
}

/* ---- lesson card ---- */
.st-key-lesson-card {
    max-width: 42rem;
    margin: 0 auto;
    padding: 1.75rem 2rem;
    background: #FFFFFF;
    border-radius: 1.25rem;
    box-shadow: 0 16px 40px -28px rgba(28, 25, 23, 0.35);
}
.lesson-difficulty-badge {
    display: inline-block;
    font: 600 0.7rem/1 "Plus Jakarta Sans", sans-serif;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    background: #FDBA74;
    color: #5A2C0A;
    padding: 0.3rem 0.65rem;
    border-radius: 999px;
    margin-bottom: 0.5rem;
}

/* ---- chat bubbles: user (amber-tinted) vs assistant (bordered white) ---- */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
    background: #FFEDD5;
    border-radius: 14px 14px 4px 14px;
    padding: 0.65rem 0.9rem;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stChatMessageContent"] {
    background: #FFFFFF;
    border: 1px solid #EDE7E0;
    border-radius: 14px 14px 14px 4px;
    padding: 0.65rem 0.9rem;
}

/* ---- correction card: success-tinted, not a plain gray box ---- */
[class*="st-key-"][class*="_correction_"] {
    background: #F0FBF4 !important;
    border-color: #BBF0CE !important;
}

/* ---- chat send button: match the docked mic button's circular shape ---- */
[data-testid="stChatInputSubmitButton"] {
    border-radius: 50% !important;
}
</style>
"""


def render_global_styles() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
