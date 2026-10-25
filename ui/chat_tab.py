"""Tab 1: book by chat (judges' Part 1), with a guided form when there's no API key."""

from __future__ import annotations

import streamlit as st

import chat_state
from llm import client as llm_client
from llm import extract
from ui import guided_form, panel, results

WELCOME = ("Hi! Tell me about your shipment in your own words: what you're sending, where it's going and when. "
           "I'll only ask for what's missing.\n\n"
           "For example: *\"3 pallets of mugs from London to a warehouse in Berlin next Thursday, cheapest please.\"*")
EXAMPLES = [
    "I need to send some mugs to Germany next week",
    "We're Northfield Goods in London. 1,080 ceramic mugs at £5 each, 12 per carton, 0.5 kg each, made in the UK, "
    "HS 691200. 3 pallets, 620 kg, to our warehouse in Berlin, appointment booked, ready 05-11-2026, cheapest.",
]


def _init() -> dict:
    if "chat" not in st.session_state:
        st.session_state.chat = {"state": chat_state.new_state(), "messages": [{"role": "assistant", "content": WELCOME}],
                                 "result": None, "last_question": "", "turns": 0, "form_step": 0}
    return st.session_state.chat


def _reset() -> None:
    st.session_state.pop("chat", None)
    for k in [k for k in st.session_state if str(k).startswith("gf_")]:
        st.session_state.pop(k, None)


def apply_and_recheck(chat: dict, new_state: dict, changes: list[str]) -> list[str]:
    """Store a new state, re-run the engine and return the result diff."""
    old = chat.get("result")
    if changes:
        new_state["confirmed"] = False
    chat["state"] = new_state
    chat["result"] = panel.compute(chat)
    return chat_state.result_diff(old, chat["result"]) if old is not None else []


def _handle(chat: dict, message: str) -> None:
    chat["messages"].append({"role": "user", "content": message})
    patch = extract.extract(message, chat["state"], chat["last_question"])
    if patch is None:
        chat["messages"].append({"role": "assistant", "content":
                                 f"Sorry, I couldn't process that just now ({llm_client.last_error or 'AI unavailable'}). "
                                 "Please try again, or switch on **Use the step-by-step form** above."})
        return
    new_state, changes, problems = chat_state.apply_patch(chat["state"], patch)
    diff = apply_and_recheck(chat, new_state, changes)
    chat["turns"] += 1
    reply = chat_state.build_reply(chat["state"], changes, problems, patch.get("reply_hint"))
    note = ""
    if chat["turns"] > 1 and changes:
        note = "Updated: " + " · ".join((changes + diff)[:8])
    chat["messages"].append({"role": "assistant", "content": reply, "note": note})
    chat["last_question"] = " ".join(chat_state.questions(chat["state"]))


def _on_apply(chat: dict):
    def apply(action: dict) -> None:
        new_state, changes, problems = chat_state.apply_fix_action(chat["state"], action)
        diff = apply_and_recheck(chat, new_state, changes)
        if changes:
            chat["messages"].append({"role": "assistant", "content": "Done. I've applied that fix and re-run the checks.",
                                     "note": "Updated: " + " · ".join(changes + diff)})
        if problems:
            chat["messages"].append({"role": "assistant", "content": " ".join(problems)})
        st.rerun()
    return apply


def _chat_ui(chat: dict) -> None:
    box = st.container(height=460)
    with box:
        for m in chat["messages"]:
            with st.chat_message(m["role"], avatar="🧑‍💼" if m["role"] == "user" else "📦"):
                st.markdown(m["content"])
                if m.get("note"):
                    st.caption("🔄 " + m["note"])
    if chat["turns"] == 0:
        st.caption("Try an example:")
        cols = st.columns(len(EXAMPLES))
        for i, ex in enumerate(EXAMPLES):
            if cols[i].button(("Vague start: " if i == 0 else "All in one: ") + ex[:38] + "…", key=f"ex{i}",
                              width="stretch", help=ex):
                with st.spinner("Reading your message…"):
                    _handle(chat, ex)
                st.rerun()
    msg = st.chat_input("Describe your shipment, or change something (e.g. \"make it 4 pallets\")")
    if msg:
        with st.spinner("Reading your message…"):
            _handle(chat, msg.strip()[:2000])
        st.rerun()


def render() -> None:
    chat = _init()
    if chat.get("result") is not None or chat["state"]["items"]:
        chat["result"] = panel.compute(chat)  # always reflect the current state (engine is fast; AI reviews cached)
    has_ai = llm_client.available()
    top = st.columns([3, 1])
    with top[0]:
        if has_ai:
            use_form = st.toggle("Use the step-by-step form instead of chat", key="use_form")
        else:
            use_form = True
            st.info("The AI chat assistant isn't switched on here (no API key), so here's a step-by-step form. "
                    "It collects the same details and runs exactly the same checks.", icon="📝")
    with top[1]:
        if st.button("🔄 Start over", width="stretch"):
            _reset()
            st.rerun()

    left, right = st.columns([3, 2], gap="large")
    with right:
        panel.render(chat)
    with left:
        if use_form:
            guided_form.render(chat, apply_and_recheck)
        else:
            _chat_ui(chat)

    state, res = chat["state"], chat.get("result")
    if res is not None and chat_state.is_complete(state):
        st.divider()
        st.subheader("Your booking check")
        confirmed = bool(state.get("confirmed"))
        results.render(res, key="chat", on_apply=_on_apply(chat), show_confirmation=confirmed, confirmed=confirmed)
        if not confirmed:
            with st.container(border=True):
                st.markdown("**Happy with this?** Confirm to see your booking confirmation and next steps. "
                            "You can still change anything afterwards.")
                if st.button("✅ Confirm booking", type="primary", key="confirm"):
                    chat["state"]["confirmed"] = True
                    st.rerun()
