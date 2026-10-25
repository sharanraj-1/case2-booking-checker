"""Live side panel: current booking, items, missing fields and live checks."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import chat_state
import engine
from engine import FIELD_LABELS, kg, money, num
from ui.style import RULE_CELL, STATUS_CHIP, chip, kv


def compute(chat: dict) -> engine.BookingResult:
    from llm import r06
    b, items = chat_state.engine_input(chat["state"])
    res = engine.check_booking(b, items, engine.today_london())
    return r06.review(res)


def render(chat: dict) -> None:
    state, res = chat["state"], chat.get("result")
    b = state["booking"]
    derived = set(state.get("derived", []))
    missing = set(chat_state.missing_fields(state))
    with st.container(border=True):
        head = "**Your booking**"
        if res is not None and chat_state.is_complete(state):
            cls, label = STATUS_CHIP[res.status]
            head += " " + chip(label, cls)
        elif state["items"] or len(b) > 3:
            head += " " + chip("In progress", "chip-blue")
        st.markdown(head, unsafe_allow_html=True)

        def val(key, fmt=str):
            v = b.get(key)
            return "" if engine.is_blank(v) else fmt(v)

        dest = ", ".join(x for x in (b.get("dest_city"), b.get("dest_country")) if x)
        rows = [
            kv("Seller", val("seller"), "seller" in missing),
            kv("From", f"{b.get('origin_city') or '?'}, United Kingdom", "origin_city" in missing),
            kv("To", dest, "dest_country" in missing or (not b.get("dest_city"))),
            kv("Delivering to", val("dest_type"), "dest_type" in missing),
        ]
        if b.get("dest_type") == "Warehouse":
            rows.append(kv("Delivery appointment booked", val("appointment"), "appointment" in missing))
        rows += [
            kv("Ready to ship", val("ready_date"), "ready_date" in missing),
            kv("Priority", val("priority"), "priority" in missing),
            kv("Pallets", val("pallets", num), "pallets" in missing),
            kv("Gross weight", val("gross_kg", kg), "gross_kg" in missing),
            kv("Cartons" + (" (calculated)" if "cartons" in derived else ""), val("cartons", num) or "from items"),
            kv("Declared value" + (" (calculated)" if "declared_value" in derived else ""),
               val("declared_value", money) or "from items"),
        ]
        st.markdown("".join(rows), unsafe_allow_html=True)

        if state["items"]:
            df = pd.DataFrame([{
                "#": i + 1, "Description": it.get("description"), "HS code": it.get("hs_code"),
                "Qty": it.get("qty"), "£/unit": it.get("unit_price"), "Units/ctn": it.get("units_per_carton"),
                "Cartons": it.get("cartons"), "kg/unit": it.get("unit_kg"), "Origin": it.get("coo"),
            } for i, it in enumerate(state["items"])])
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.markdown('<div class="muted">No items yet.</div>', unsafe_allow_html=True)

        need = [FIELD_LABELS.get(k, "Items") if k != "items" else "What you're sending" for k in chat_state.missing_fields(state)]
        for idx, miss in chat_state.missing_item_fields(state):
            label = state["items"][idx].get("description") or f"item {idx + 1}"
            need.append(f"{label}: " + ", ".join(FIELD_LABELS[f].lower() for f in miss))
        if need:
            st.markdown("**Still needed:** " + "; ".join(need))
        else:
            st.markdown("**Nothing missing.** ✅")

        if res is not None:
            cells = "".join(
                f'<div class="rulecell" title="{engine.RULES[r]["name"]}">{RULE_CELL[s]} {r} '
                f'<span class="muted">{"needs info" if s == "Data" else ("pass" if s == "Pass" else s)}</span></div>'
                for r, s in res.rule_status.items())
            st.markdown("**Live checks**" + f'<div class="rulegrid">{cells}</div>', unsafe_allow_html=True)
            if res.recommendation and b.get("dest_country"):
                st.markdown(f"⭐ **{res.recommendation}** · {money(res.total_cost)} · delivery "
                            f"{engine.format_date(res.eta)}")
