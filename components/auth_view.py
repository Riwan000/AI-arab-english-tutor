"""Login/signup screen — gates app.py's routing until the user is authenticated."""

import streamlit as st

import api_client


def _on_authenticated(result: dict, cookie_manager) -> None:
    token = result["access_token"]
    api_client.set_auth_token(token)
    cookie_manager.set("auth_token", token)
    st.session_state.user = result["user"]
    st.rerun()


RTL_AUTH_CSS = '<style>.st-key-auth-rtl { direction: rtl; text-align: right; }</style>'


def render_auth_view(cookie_manager) -> None:
    with st.container(key="auth-rtl"):
        st.markdown(RTL_AUTH_CSS, unsafe_allow_html=True)
        st.title("📚 معلم اللغة الإنجليزية")

        tab_login, tab_signup = st.tabs(["تسجيل الدخول", "إنشاء حساب"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("البريد الإلكتروني", key="login_email")
                password = st.text_input(
                    "كلمة المرور", type="password", key="login_password"
                )
                if st.form_submit_button("تسجيل الدخول", use_container_width=True):
                    if not email or not password:
                        st.error("الرجاء إدخال البريد الإلكتروني وكلمة المرور.")
                    else:
                        result = api_client.login(email, password)
                        if result:
                            _on_authenticated(result, cookie_manager)

        with tab_signup:
            with st.form("signup_form"):
                display_name = st.text_input("الاسم المعروض", key="signup_display_name")
                email = st.text_input("البريد الإلكتروني", key="signup_email")
                password = st.text_input(
                    "كلمة المرور",
                    type="password",
                    key="signup_password",
                    help="8 أحرف على الأقل.",
                )
                if st.form_submit_button("إنشاء حساب", use_container_width=True):
                    if not display_name or not email or not password:
                        st.error("الرجاء تعبئة جميع الحقول.")
                    else:
                        result = api_client.signup(email, password, display_name)
                        if result:
                            _on_authenticated(result, cookie_manager)
