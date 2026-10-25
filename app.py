"""Pallet Pre-Flight: conversational UK -> EU shipment booking and pre-flight error checker.

Run: streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="Pallet Pre-Flight", page_icon="📦", layout="wide")

import engine  # noqa: E402
from llm import client as llm_client  # noqa: E402
from ui import chat_tab, file_tab, style  # noqa: E402

style.inject()

head, side = st.columns([4, 1.4])
with head:
    st.title("📦 Pallet Pre-Flight")
    st.markdown("Book a UK → EU pallet shipment and catch paperwork mistakes **before** it leaves. "
                "Every booking is checked against the 10 rules (R-01 to R-10), gets a carrier recommendation "
                "based on your priority, and a plain-English confirmation.")
with side:
    ai = llm_client.available()
    st.markdown(style.chip("AI assistant: on" if ai else "AI assistant: off (form mode)",
                           "chip-green" if ai else "chip-adv"), unsafe_allow_html=True)
    st.caption(f"Today (London): {engine.format_date(engine.today_london())}")
    style.glossary()

tab_chat, tab_file = st.tabs(["💬 Book by chat", "📄 Check a file"])
with tab_chat:
    try:
        chat_tab.render()
    except Exception as e:  # never show a stack trace to a seller
        st.error(f"Something went wrong on this tab ({type(e).__name__}). Press **Start over** and try again.")
with tab_file:
    try:
        file_tab.render()
    except Exception as e:
        st.error(f"Something went wrong reading that file ({type(e).__name__}). Please check the file and try again.")

st.divider()
st.caption("Rules, statuses, carrier choice and delivery dates come from a fixed rulebook and rate card, calculated in "
           "code. The AI only reads your messages and explains; it never decides a result. Prices are the fixed "
           "rate card, not live quotes. Delivery dates are estimates in working days.")
