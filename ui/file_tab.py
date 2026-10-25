"""Tab 2: check a file of bookings (judges' Part 2)."""

from __future__ import annotations

import copy
import hashlib
import os

import pandas as pd
import streamlit as st

import chat_state
import engine
from llm import client as llm_client
from llm import r06
from ui import export, results

SAMPLE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_bookings.xlsx")


@st.cache_data(show_spinner=False, max_entries=20)
def _parse(names: tuple[str, ...], blobs: tuple[bytes, ...]):
    import io
    if len(blobs) == 1 and names[0].lower().endswith(".xlsx"):
        return engine.load_workbook(io.BytesIO(blobs[0]))
    if len(blobs) == 2 and all(n.lower().endswith(".csv") for n in names):
        # Put the file named like "booking" first; the loader also swaps them if needed.
        pairs = sorted(zip(names, blobs), key=lambda p: 0 if "booking" in p[0].lower() else 1)
        return engine.load_csvs(io.BytesIO(pairs[0][1]), io.BytesIO(pairs[1][1]))
    return [], [], [{"level": "error", "message":
                     "Please upload one .xlsx file (with Bookings and Items sheets) or two .csv files (Bookings and Items)."}]


def _load(names: list[str], blobs: list[bytes], label: str) -> None:
    try:
        bookings, items, notices = _parse(tuple(names), tuple(blobs))
    except Exception as e:  # the loader shouldn't raise, but never crash the page
        bookings, items, notices = [], [], [{"level": "error", "message": f"Couldn't read the file ({type(e).__name__})."}]
    st.session_state.file = {"label": label, "bookings": bookings, "items": items, "notices": notices, "edits": {}}
    st.session_state.pop("file_selected", None)


def _items_for(data: dict, booking: dict) -> list[dict]:
    key = booking.get("_match_id") or str(booking.get("booking_id") or "").strip().upper()
    return [i for i in data["items"] if str(i.get("booking_id") or "").strip().upper() == key]


def _results(data: dict) -> list[engine.BookingResult]:
    today = engine.today_london()
    out = engine.check_all(data["bookings"], data["items"], today, data["notices"])
    for idx, res in enumerate(out):
        edit = data["edits"].get(res.booking_id)
        if edit:
            res = engine.check_booking(edit["booking"], edit["items"], today)
            res.notices = [{"message": "Edited here: " + "; ".join(edit["log"]) + ". Your uploaded file is unchanged."}]
        out[idx] = r06.review(res)
    return out


def _apply_fix(data: dict, res: engine.BookingResult, action: dict) -> None:
    """File mode: change only the one value the seller clicked, on an in-app copy."""
    edit = data["edits"].get(res.booking_id)
    if edit is None:
        raw = next(b for b in data["bookings"] if b.get("booking_id") == res.booking_id)
        edit = {"booking": copy.deepcopy(raw), "items": copy.deepcopy(_items_for(data, raw)), "log": []}
    state = {"booking": edit["booking"], "items": edit["items"], "derived": []}
    new, changes, problems = chat_state.apply_fix_action(state, action, derive=False)
    if changes:
        edit.update(booking=new["booking"], items=new["items"])
        edit["log"] += changes
        data["edits"][res.booking_id] = edit
    if problems:
        st.session_state.file_flash = " ".join(problems)


def render() -> None:
    st.markdown("Upload your **Bookings** and **Items** sheets to check every booking against the 10 rules, "
                "see what to fix, and get a carrier recommendation for each.")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("▶️ Try sample file", type="primary", width="stretch",
                     help="Loads test_bookings.xlsx: 18 bookings with one planted mistake per rule."):
            with open(SAMPLE_PATH, "rb") as fh:
                _load(["test_bookings.xlsx"], [fh.read()], "Sample file (test_bookings.xlsx)")
    with c2:
        try:
            with open(SAMPLE_PATH, "rb") as fh:
                st.download_button("⬇️ Download the sample / template", fh.read(), file_name="test_bookings.xlsx",
                                   width="stretch")
        except OSError:
            pass
    uploads = st.file_uploader("Upload one .xlsx (Bookings + Items sheets) or two .csv files",
                               type=["xlsx", "csv"], accept_multiple_files=True)
    if uploads:
        blobs = [u.getvalue() for u in uploads]
        digest = hashlib.sha1(b"".join(blobs)).hexdigest()
        if st.session_state.get("file_digest") != digest:
            st.session_state.file_digest = digest
            _load([u.name for u in uploads], blobs, ", ".join(u.name for u in uploads))

    data = st.session_state.get("file")
    if not data:
        st.caption("Dates are read as DD-MM-YYYY. HS codes are read as text, so keep the column formatted as Text "
                   "to protect leading zeros.")
        return

    st.markdown(f"**Checking:** {data['label']}")
    errors = [n for n in data["notices"] if n.get("level") == "error"]
    for n in errors:
        st.error(n["message"])
    warnings = [n for n in data["notices"] if n.get("level") != "error"]
    if warnings:
        with st.expander(f"⚠️ {len(warnings)} file note{'s' if len(warnings) != 1 else ''} (orphan items, duplicates, missing columns)",
                         expanded=True):
            for n in warnings:
                st.markdown(f"- {n['message']}")
    if not data["bookings"]:
        st.info("No bookings found to check.")
        return

    if llm_client.available():
        with st.spinner("Checking bookings (AI is reviewing any unclear product descriptions)…"):
            res_list = _results(data)
    else:
        res_list = _results(data)
    counts = engine.status_counts(res_list)

    m = st.columns(4)
    m[0].metric("Bookings", len(res_list))
    m[1].metric("🔴 Blocked", counts["Blocked"], help="At least one Red or missing-data problem. Fix before collection.")
    m[2].metric("🟠 Ready with warnings", counts["Ready with warnings"], help="Only Amber warnings: bookable, but may cause delays or charges.")
    m[3].metric("🟢 Ready", counts["Ready"], help="All 10 checks passed.")

    df = pd.DataFrame(export.summary_rows(res_list))
    df["Cost (£)"] = df["Cost (£)"].map(lambda v: "—" if v is None or pd.isna(v) else f"£{v:,.0f}")
    st.markdown("**Click a row to open that booking.**")
    event = st.dataframe(df, hide_index=True, width="stretch", on_select="rerun",
                         selection_mode="single-row", key="summary_table",
                         column_config={"Status": st.column_config.TextColumn("Status", width="medium"),
                                        "Red": st.column_config.NumberColumn("🔴 Red", help="Red + missing-data problems"),
                                        "Amber": st.column_config.NumberColumn("🟠 Amber")})
    ids = [r.booking_id for r in res_list]
    rows = tuple(event.selection.rows) if event and event.selection else ()
    if rows and rows != st.session_state.get("file_rows") and rows[0] < len(ids):
        st.session_state.file_selected = ids[rows[0]]  # a new row click wins over the dropdown
    st.session_state.file_rows = rows
    current = st.session_state.get("file_selected")
    if current not in ids:
        current = next((r.booking_id for r in res_list if r.status == "Blocked"), ids[0])
    pick = st.selectbox("Booking", ids, index=ids.index(current),
                        format_func=lambda i: f"{i} · {next(r for r in res_list if r.booking_id == i).status}")
    st.session_state.file_selected = pick

    st.download_button("⬇️ Download results (.xlsx)", export.to_xlsx(res_list),
                       file_name="preflight_results.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    res = next(r for r in res_list if r.booking_id == pick)
    st.divider()
    st.subheader(f"{pick} · {res.booking.get('seller') or ''}")
    if st.session_state.get("file_flash"):
        st.warning(st.session_state.pop("file_flash"))

    def on_apply(action, _res=res):
        _apply_fix(data, _res, action)
        st.rerun()

    results.render(res, key=f"file-{pick}", on_apply=on_apply)
    if pick in data["edits"] and st.button("↩️ Undo my edits to this booking", key=f"undo-{pick}"):
        data["edits"].pop(pick, None)
        st.rerun()
