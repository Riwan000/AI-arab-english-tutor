"""HTTP client for the FastAPI backend — used by Streamlit components."""

import streamlit as st


def base_url() -> str:
    """Return BACKEND_URL from Streamlit secrets, with local default."""
    return st.secrets.get("BACKEND_URL", "http://localhost:8000")
