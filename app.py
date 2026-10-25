"""Pallet Pre-Flight: conversational UK -> EU shipment booking and pre-flight error checker.

The whole interface is a React component (pallet_ui/frontend). Python keeps the state,
runs every check through engine.py (via bridge.py) and hands the UI a plain-English payload.

Run: streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="Pallet Pre-Flight", page_icon="📦", layout="wide", initial_sidebar_state="collapsed")

import bridge  # noqa: E402
from llm import client as llm_client  # noqa: E402
from llm import extract, r06  # noqa: E402
from pallet_ui import pallet_ui  # noqa: E402

# Let the React app own the whole screen.
st.markdown("""
<style>
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], footer, #MainMenu {display: none !important;}
html, body, .stApp, [data-testid="stAppViewContainer"] {background: #06070a !important;}
[data-testid="stMainBlockContainer"], .block-container {padding: 0 !important; max-width: 100% !important;}
iframe[title*="pallet_ui"] {position: fixed !important; inset: 0 !important; width: 100vw !important;
  height: 100vh !important; height: 100dvh !important; border: 0 !important; z-index: 999990; background: #06070a;}
</style>
""", unsafe_allow_html=True)

AI_ON = llm_client.available()
if "sess" not in st.session_state:
    st.session_state.sess = bridge.new_session(AI_ON)
sess = st.session_state.sess
sess["ai_on"] = AI_ON


def _on_event() -> None:
    ev = st.session_state.get("pallet_ui")
    try:
        bridge.handle_event(sess, ev, extractor=extract.extract if AI_ON else None, review=r06.review)
    except Exception as e:  # never crash in front of a seller
        if isinstance(ev, dict):
            sess["last_id"] = ev.get("id")
        sess["flash"] = f"Sorry, something went wrong there ({type(e).__name__}). Please try again."


try:
    data = bridge.payload(sess, review=r06.review)
except Exception as e:
    sess["file"] = None
    sess["flash"] = f"Sorry, that file couldn't be shown ({type(e).__name__}). Please try another file."
    data = bridge.payload(sess, review=r06.review)

pallet_ui(data, key="pallet_ui", on_change=_on_event)
