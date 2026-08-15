"""Login/signup screen — gates app.py's routing until the user is authenticated."""

import streamlit as st

import api_client


def _on_authenticated(result: dict, cookie_manager) -> None:
    token = result["access_token"]
    api_client.set_auth_token(token)
    cookie_manager.set("auth_token", token)
    st.session_state.user = result["user"]
    st.rerun()


def render_auth_view(cookie_manager) -> None:
    st.title("📚 AI English Tutor")

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            if st.form_submit_button("Login", use_container_width=True):
                if not email or not password:
                    st.error("Please enter your email and password.")
                else:
                    result = api_client.login(email, password)
                    if result:
                        _on_authenticated(result, cookie_manager)

    with tab_signup:
        with st.form("signup_form"):
            display_name = st.text_input("Display name", key="signup_display_name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input(
                "Password",
                type="password",
                key="signup_password",
                help="At least 8 characters.",
            )
            if st.form_submit_button("Sign Up", use_container_width=True):
                if not display_name or not email or not password:
                    st.error("Please fill in all fields.")
                else:
                    result = api_client.signup(email, password, display_name)
                    if result:
                        _on_authenticated(result, cookie_manager)
