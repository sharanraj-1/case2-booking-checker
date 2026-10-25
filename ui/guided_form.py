"""Step-by-step form: the no-API-key version of chat booking. Same state, same checks."""

from __future__ import annotations

import copy

import pandas as pd
import streamlit as st

import chat_state
import engine

STEPS = ["Route", "Delivery & timing", "Load", "Items", "Review"]
PRIORITY_HELP = {"Cheapest": "lowest cost", "Fastest": "shortest transit", "Most reliable": "best on-time record",
                 "Balanced": "never the priciest, slowest or least reliable"}
ITEM_COLS = {"description": "Description", "hs_code": "HS code", "qty": "Quantity", "unit_price": "Unit price (£)",
             "units_per_carton": "Units per carton", "cartons": "Cartons", "unit_kg": "Unit weight (kg)",
             "coo": "Country of origin"}


def _int(v):
    return None if v is None else int(v)


def _float(v):
    return None if v is None else float(v)


def _idx(options: list, value, default=None):
    return options.index(value) if value in options else default


def _submit(chat: dict, apply_and_recheck, patch: dict, replace_items: bool = False) -> list[str]:
    state = chat["state"]
    if replace_items:
        state = copy.deepcopy(state)
        state["items"] = []
    new_state, changes, problems = chat_state.apply_patch(state, patch)
    apply_and_recheck(chat, new_state, changes or (["items"] if replace_items else []))
    return problems


def render(chat: dict, apply_and_recheck) -> None:
    step = chat.get("form_step", 0)
    b = chat["state"]["booking"]
    st.progress((step + 1) / len(STEPS), text=f"Step {step + 1} of {len(STEPS)} · {STEPS[step]}")
    patch: dict = {"booking_updates": {}}
    replace_items = False

    if step == 0:
        patch["booking_updates"]["origin_city"] = st.selectbox(
            "Collecting from (United Kingdom)", engine.ORIGIN_CITIES, index=_idx(engine.ORIGIN_CITIES, b.get("origin_city")),
            placeholder="Choose a city", key="gf_origin")
        countries = list(engine.DEST_CITIES)
        country = st.radio("Destination country", countries, index=_idx(countries, b.get("dest_country")),
                           horizontal=True, key="gf_country")
        if country:
            cities = engine.DEST_CITIES[country]
            patch["booking_updates"]["dest_country"] = country
            patch["booking_updates"]["dest_city"] = st.selectbox(
                "Destination city", cities, index=_idx(cities, b.get("dest_city")), placeholder="Choose a city",
                key=f"gf_city_{country}")
    elif step == 1:
        patch["booking_updates"]["seller"] = st.text_input("Seller (your business) name", value=b.get("seller") or "",
                                                           key="gf_seller") or None
        dtype = st.radio("Delivering to", engine.DEST_TYPES, index=_idx(engine.DEST_TYPES, b.get("dest_type")),
                         horizontal=True, key="gf_dtype",
                         help="A business address is a shop, office or other premises that isn't a warehouse.")
        patch["booking_updates"]["dest_type"] = dtype
        if dtype == "Warehouse":
            patch["booking_updates"]["appointment"] = st.radio(
                "Has a delivery appointment been booked with the warehouse?", engine.YES_NO,
                index=_idx(engine.YES_NO, b.get("appointment")), horizontal=True, key="gf_appt")
        ready = engine.parse_date(b.get("ready_date"))
        d = st.date_input("Ready to ship (DD/MM/YYYY)", value=ready, format="DD/MM/YYYY", key="gf_ready")
        patch["booking_updates"]["ready_date"] = engine.format_date(d) if d else None
        patch["booking_updates"]["priority"] = st.radio(
            "What matters most?", engine.PRIORITIES, index=_idx(engine.PRIORITIES, b.get("priority")),
            format_func=lambda p: f"{p} ({PRIORITY_HELP[p]})", key="gf_prio")
    elif step == 2:
        patch["booking_updates"]["pallets"] = st.number_input(
            "Number of pallets", min_value=1, step=1, value=_int(b.get("pallets")), placeholder="e.g. 3", key="gf_pallets")
        patch["booking_updates"]["gross_kg"] = st.number_input(
            "Total gross weight (kg)", min_value=0.0, step=10.0, value=_float(b.get("gross_kg")), placeholder="e.g. 620",
            key="gf_gross", help="Goods + cartons + packaging + pallets.")
        with st.expander("Already know the booking totals? (otherwise we calculate them from the items)"):
            derived = set(chat["state"].get("derived", []))
            patch["booking_updates"]["cartons"] = st.number_input(
                "Total cartons", min_value=1, step=1, value=None if "cartons" in derived else _int(b.get("cartons")),
                key="gf_cartons")
            patch["booking_updates"]["declared_value"] = st.number_input(
                "Total declared value (£)", min_value=0.0, step=10.0,
                value=None if "declared_value" in derived else _float(b.get("declared_value")), key="gf_value",
                help="The total value you tell customs. It must match your invoice.")
    elif step == 3:
        st.markdown("Add one row per product. Leave **Cartons** blank to calculate it from quantity ÷ units per carton.")
        rows = [{k: it.get(k) for k in ITEM_COLS} for it in chat["state"]["items"]] or [{k: None for k in ITEM_COLS}]
        df = pd.DataFrame(rows, columns=list(ITEM_COLS))
        for col in ("description", "hs_code", "coo"):
            df[col] = df[col].astype("string")
        edited = st.data_editor(
            df, num_rows="dynamic", width="stretch", key="gf_items", hide_index=True,
            column_config={
                "description": st.column_config.TextColumn("Description", required=True),
                "hs_code": st.column_config.TextColumn("HS code", help="6–10 digit customs code, e.g. 691200"),
                "qty": st.column_config.NumberColumn("Quantity", min_value=1, step=1),
                "unit_price": st.column_config.NumberColumn("Unit price (£)", min_value=0.0, format="£%.2f"),
                "units_per_carton": st.column_config.NumberColumn("Units per carton", min_value=1, step=1),
                "cartons": st.column_config.NumberColumn("Cartons", min_value=1, step=1),
                "unit_kg": st.column_config.NumberColumn("Unit weight (kg)", min_value=0.0, format="%.3f"),
                "coo": st.column_config.SelectboxColumn("Country of origin", options=engine.COO_ALLOWED),
            })
        replace_items = True
        patch["item_updates"] = []
        old_items = chat["state"]["items"]
        for n, (_, row) in enumerate(edited.iterrows()):
            fields = {k: (None if pd.isna(v) else v) for k, v in row.items()}
            old = old_items[n] if n < len(old_items) else {}
            if old.get("_cartons_derived") and fields.get("cartons") == old.get("cartons"):
                fields["cartons"] = None  # we calculated it before, so recalculate it
            if all(v in (None, "") for v in fields.values()):
                continue
            for k in ("qty", "units_per_carton", "cartons"):
                if isinstance(fields.get(k), float) and fields[k].is_integer():
                    fields[k] = int(fields[k])
            patch["item_updates"].append({"op": "add", "fields": fields})
    else:
        missing = chat_state.questions(chat["state"], limit=10)
        if missing:
            st.warning("A few things are still missing:\n\n" + "\n".join(f"- {q}" for q in missing))
        else:
            st.success("All details are in. Your checks and carrier recommendation are below.")

    patch["booking_updates"] = {k: v for k, v in patch["booking_updates"].items() if v not in (None, "")}
    c1, c2 = st.columns(2)
    if step > 0 and c1.button("← Back", width="stretch", key=f"gf_back{step}"):
        _submit(chat, apply_and_recheck, patch, replace_items) if step < 4 else None
        chat["form_step"] = step - 1
        st.rerun()
    if step < len(STEPS) - 1 and c2.button("Next →", type="primary", width="stretch", key=f"gf_next{step}"):
        problems = _submit(chat, apply_and_recheck, patch, replace_items)
        if problems:
            st.session_state.gf_problems = problems
        chat["form_step"] = step + 1
        st.rerun()
    for p in st.session_state.pop("gf_problems", []):
        st.warning(p)
