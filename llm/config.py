"""LLM settings in one place. All AI calls go through OpenRouter (OpenAI-compatible API)."""

import os

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-3.8-flash"  # Gemini via OpenRouter; supports JSON output
REASONING_EFFORT = "low"           # extraction and classification are simple; keeps replies fast
MAX_TOKENS = 2000
TIMEOUT_SECONDS = 25
APP_TITLE = "Pallet Pre-Flight"
KEY_NAME = "OPENROUTER_API_KEY"


def get_api_key() -> str | None:
    """OPENROUTER_API_KEY from Streamlit secrets, then the environment. None if absent."""
    if os.environ.get("PALLET_NO_AI"):  # force guided mode (tests, demos without AI)
        return None
    try:
        import streamlit as st
        key = st.secrets.get(KEY_NAME)
        if key:
            return str(key).strip()
    except Exception:
        pass  # no secrets.toml, or not running under Streamlit
    key = os.environ.get(KEY_NAME, "").strip()
    if not key:
        try:  # plain scripts and tests: read the local secrets file directly
            import tomllib
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".streamlit", "secrets.toml")
            with open(path, "rb") as fh:
                key = str(tomllib.load(fh).get(KEY_NAME, "")).strip()
        except Exception:
            key = ""
    return key or None
