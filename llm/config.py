"""LLM settings in one place."""

import os

MODEL = "claude-opus-5-5"
EFFORT = "low"  # extraction and classification are simple; keeps replies fast
MAX_TOKENS = 4000
TIMEOUT_SECONDS = 30
# Server-side fallback if the model declines a request (refusal) - see README.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def get_api_key() -> str | None:
    """ANTHROPIC_API_KEY from Streamlit secrets, then the environment. None if absent."""
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY")
        if key:
            return str(key).strip()
    except Exception:
        pass  # no secrets.toml, or not running under Streamlit
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return key or None
