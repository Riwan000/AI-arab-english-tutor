"""Login/signup screen — gates app.py's routing until the user is authenticated."""

import streamlit as st

import api_client
import i18n


def _on_authenticated(result: dict, cookie_manager) -> None:
    token = result["access_token"]
    st.session_state.auth_token = token
    api_client.set_auth_token(token)
    cookie_manager.set("auth_token", token)
    st.session_state.user = result["user"]
    st.rerun()


def render_auth_view(cookie_manager) -> None:
    i18n.render_language_switcher(cookie_manager, key="auth_lang")

    with st.container(key="auth-rtl"):
        st.markdown(i18n.rtl_style(".st-key-auth-rtl"), unsafe_allow_html=True)
        st.title(i18n.t("app_title"))

        tab_login, tab_signup = st.tabs([i18n.t("tab_login"), i18n.t("tab_signup")])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input(i18n.t("email_label"), key="login_email")
                password = st.text_input(
                    i18n.t("password_label"), type="password", key="login_password"
                )
                if st.form_submit_button(i18n.t("login_button"), use_container_width=True):
                    if not email or not password:
                        st.error(i18n.t("login_validation_error"))
                    else:
                        result = api_client.login(email, password)
                        if result:
                            _on_authenticated(result, cookie_manager)

        with tab_signup:
            with st.form("signup_form"):
                display_name = st.text_input(
                    i18n.t("display_name_label"), key="signup_display_name"
                )
                email = st.text_input(i18n.t("email_label"), key="signup_email")
                password = st.text_input(
                    i18n.t("password_label"),
                    type="password",
                    key="signup_password",
                    help=i18n.t("password_help"),
                )
                if st.form_submit_button(i18n.t("signup_button"), use_container_width=True):
                    if not display_name or not email or not password:
                        st.error(i18n.t("signup_validation_error"))
                    else:
                        result = api_client.signup(email, password, display_name)
                        if result:
                            _on_authenticated(result, cookie_manager)
