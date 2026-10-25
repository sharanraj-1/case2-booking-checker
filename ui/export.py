"""Download results as .xlsx (summary sheet + findings sheet + carrier options)."""

from __future__ import annotations

import io

import pandas as pd

import engine
from engine import format_date

STATUS_EMOJI = {"Blocked": "🔴", "Ready with warnings": "🟠", "Ready": "🟢"}


def route(r: engine.BookingResult) -> str:
    b = r.booking
    return f"{b.get('origin_city') or '?'} → {b.get('dest_city') or '?'}, {b.get('dest_country') or '?'}"


def summary_rows(results: list[engine.BookingResult]) -> list[dict]:
    return [{
        "Booking ID": r.booking_id,
        "Seller": r.booking.get("seller") or "",
        "Route": route(r),
        "Status": f"{STATUS_EMOJI.get(r.status, '')} {r.status}",
        "Red": r.red_count + r.data_count,
        "Amber": r.amber_count,
        "Carrier": r.recommendation or "—",
        "Cost (£)": r.total_cost,
        "ETA": format_date(r.eta),
    } for r in results]


def to_xlsx(results: list[engine.BookingResult]) -> bytes:
    summary = pd.DataFrame([{
        **{k: v for k, v in row.items() if k not in ("Red", "Amber", "Status", "Carrier", "Cost (£)", "ETA")},
        "Status": r.status,
        "Red (must fix)": r.red_count,
        "Data issues": r.data_count,
        "Amber (warnings)": r.amber_count,
        "Advisory": r.count("Advisory"),
        "Rules passed": f"{len(r.rules_passed)}/10",
        "Recommended carrier": r.recommendation or "—",
        "Cost (£)": r.total_cost,
        "Collection date": format_date(r.collection_date),
        "Estimated delivery": format_date(r.eta),
        "Why this carrier": r.reason,
    } for row, r in zip(summary_rows(results), results)])
    findings = pd.DataFrame([{
        "Booking ID": r.booking_id, "Rule": f.rule_id, "Severity": f.severity, "SKU": f.sku or "",
        "What's wrong": f.message, "How to fix": f.fix,
    } for r in results for f in r.findings], columns=["Booking ID", "Rule", "Severity", "SKU", "What's wrong", "How to fix"])
    options = pd.DataFrame([{
        "Booking ID": r.booking_id, "Carrier": o.carrier, "Service": o.service,
        "Recommended": "Yes" if o.carrier == r.recommendation else "",
        "Eligible": {True: "Yes", False: "No", None: "Unknown"}[o.eligible],
        "Cost (£)": o.cost, "Pallets needed": o.pallets_needed, "Cost if re-palletised (£)": o.cost_if_repalletised,
        "Transit (working days)": o.transit_days, "On time %": o.on_time, "Max kg/pallet": o.max_kg,
        "Est. delivery": format_date(o.eta), "Excluded because": o.excluded_reason,
    } for r in results for o in r.options])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="Summary", index=False)
        findings.to_excel(xw, sheet_name="Findings", index=False)
        options.to_excel(xw, sheet_name="Carrier options", index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col[:50])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 70)
    return buf.getvalue()
