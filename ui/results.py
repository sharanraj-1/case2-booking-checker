"""The shared results component, used for every booking from either tab.

It only displays what engine.BookingResult says; it never decides anything.
"""

from __future__ import annotations

from html import escape
from typing import Callable

import pandas as pd
import streamlit as st

import engine
from engine import FIELD_LABELS, format_date, kg, money, num
from ui.style import SEV_CHIP, STATUS_CHIP, abbr, chip

GROUPS = [("Red", "Must fix before it can ship"), ("Data", "Missing or unreadable information"),
          ("Amber", "Warnings to sort out"), ("Advisory", "Advisory / reference only")]
INVOICE_GUIDE = "https://www.gov.uk/guidance/international-trade-paperwork-the-basics"


def _rule_title(f: engine.Finding) -> str:
    if f.rule_id in engine.RULES:
        return f"{f.rule_id} · {engine.RULES[f.rule_id]['name']}"
    return {"DATA": "Data check", "ADVICE": "Advisory"}.get(f.rule_id, f.rule_id)


def fix_label(action: dict) -> str:
    field, value = action["field"], action["value"]
    if field == "declared_value":
        shown = money(value)
    elif field == "gross_kg":
        shown = kg(value)
    elif field in ("hs_code", "ready_date"):
        shown = str(value)
    else:
        shown = num(value)
    where = f" for {action['sku']}" if action.get("target") == "item" and action.get("sku") else ""
    label = FIELD_LABELS.get(field, field)
    label = label if label.startswith("HS") else label.lower()
    return f"Apply this fix: set {label}{where} to {shown}"


def status_banner(res: engine.BookingResult) -> None:
    blockers = res.red_count + res.data_count
    passed = len(res.rules_passed)
    if res.status == "Blocked":
        st.error(f"**Blocked: {blockers} problem{'s' if blockers != 1 else ''} must be fixed before this can ship.** "
                 f"{passed} of 10 checks passed.", icon="🔴")
    elif res.status == "Ready with warnings":
        st.warning(f"**Ready with warnings: {res.amber_count} thing{'s' if res.amber_count != 1 else ''} to sort out "
                   f"before collection.** It can be booked, but these may cause delays or charges.", icon="🟠")
    else:
        st.success("**Ready to book: all 10 checks passed.**", icon="🟢")


def findings(res: engine.BookingResult, key: str, on_apply: Callable[[dict], None] | None) -> None:
    if not res.findings:
        st.markdown("No problems found. Every rule from R-01 to R-10 passed.")
        return
    for sev, heading in GROUPS:
        group = [f for f in res.findings if f.severity == sev]
        if not group:
            continue
        cls, label = SEV_CHIP[sev]
        st.markdown(f"{chip(label, cls)} <b>{escape(heading)}</b> ({len(group)})", unsafe_allow_html=True)
        for i, f in enumerate(group):
            with st.container(border=True):
                st.markdown(f"**{_rule_title(f)}**" + (f"  ·  SKU {f.sku}" if f.sku else ""))
                st.markdown(f"**What's wrong:** {f.message}")
                why = engine.RULES.get(f.rule_id, {}).get("why")
                if why and sev != "Advisory":
                    st.markdown(f"**Why it matters:** {why}")
                st.markdown(f"**How to fix:** {f.fix}")
                ai = f.meta.get("ai")
                if ai:
                    if ai["contains_dg"] == "no":
                        st.caption(f"🤖 AI review: likely safe. {ai.get('why', '')}")
                    elif ai["contains_dg"] == "unsure":
                        st.caption(f"🤖 AI review: unsure. {ai.get('why', '')}")
                    else:
                        st.caption("🤖 AI review thinks this is restricted; see the Red flag above.")
                if f.meta.get("source") == "ai":
                    st.caption("This flag comes from an AI review of the description, not a fixed rule. Please confirm it.")
                if on_apply and f.fix_action:
                    if st.button(fix_label(f.fix_action), key=f"{key}-fix-{sev}-{i}", type="secondary"):
                        on_apply(f.fix_action)


def carriers(res: engine.BookingResult) -> None:
    if not res.options:
        st.info(res.reason or "No carrier options yet.")
        return
    rows = []
    for o in res.options:
        if o.eligible:
            cost = money(o.cost)
            state = "✅ Can carry"
        elif o.eligible is None:
            cost = money(o.cost) if o.cost is not None else f"{money(o.price_per_pallet)} / pallet"
            state = "❔ Weight unknown"
        else:
            cost = f"{money(o.cost_if_repalletised)} on {o.pallets_needed} pallets" if o.cost_if_repalletised else "—"
            state = "❌ " + (o.excluded_reason.split(": ", 1)[-1] if ": " in o.excluded_reason else o.excluded_reason)
        rows.append({
            "": "⭐ Pick" if o.carrier == res.recommendation else "",
            "Carrier": f"{o.carrier} ({o.service})",
            "Cost": cost,
            "Transit": f"{o.transit_days} working days",
            "On time": f"{o.on_time}%",
            "Max per pallet": f"{o.max_kg} kg",
            "Est. delivery": format_date(o.eta),
            "Can it take this load?": state,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    pallets = res.booking.get("pallets")
    wpp = f"Load: {kg(res.booking.get('gross_kg'))} on {num(pallets)} pallet{'' if pallets == 1 else 's'}"
    if res.weight_per_pallet:
        wpp += f" = **{kg(res.weight_per_pallet)} per pallet**"
    prio = res.booking.get("priority") if res.booking.get("priority") in engine.PRIORITIES else "Balanced"
    st.markdown(f"{wpp}  ·  Seller priority: **{prio}**")
    if res.recommendation:
        st.info(f"**Recommended: {res.recommendation}.** {res.reason}", icon="⭐")
        if res.why_others_lost:
            st.markdown("**Why not the others:**\n" + "\n".join(f"- {w}" for w in res.why_others_lost))
    if prio == "Balanced":
        st.caption("Balanced uses minimax regret: for cost, speed and reliability we measure how far each carrier is "
                   "from the best option, and pick the one whose worst gap is smallest. Equal-weight scoring would "
                   "always pick the most expensive carrier, which isn't balanced.")


def _summary_line(res: engine.BookingResult) -> str:
    b = res.booking
    pallets = b.get("pallets")
    return (f"{b.get('seller') or 'Seller'}: {num(pallets) if pallets else '?'} pallet{'s' if pallets != 1 else ''}, "
            f"{b.get('origin_city') or '?'} → {b.get('dest_city') or '?'}, {b.get('dest_country') or '?'} "
            f"({b.get('dest_type') or 'delivery type?'})")


def confirmation(res: engine.BookingResult, confirmed: bool = False) -> None:
    opt = res.chosen_option
    b = res.booking
    with st.container(border=True):
        if res.status == "Blocked":
            st.markdown("### ⛔ Not booked yet")
            st.markdown(_summary_line(res))
            st.markdown("**Fix these first:**\n" + "\n".join(
                f"{i}. {f.fix}" + (f" ({f.sku})" if f.sku else "")
                for i, f in enumerate([f for f in res.findings if f.severity in ("Red", "Data")], 1)))
            if opt:
                pallets = opt.pallets_needed if not opt.eligible else opt.pallets
                st.markdown(f"**Provisional:** {opt.carrier} ({opt.service}) at about **{money(res.total_cost)}**"
                            f"{f' for {pallets} pallet' + ('' if pallets == 1 else 's') if pallets else ''}, collection {format_date(res.collection_date)}, "
                            f"delivery around **{format_date(res.eta)}**. The carrier, cost and date may change once the "
                            "problems are fixed.")
            return
        st.markdown("### ✅ Booking confirmed" if confirmed else "### 📋 Booking summary (ready to confirm)")
        st.markdown(_summary_line(res))
        lines = [
            f"**Carrier:** {opt.carrier} ({opt.service}), {opt.transit_days} working days, {opt.on_time}% on time",
            f"**Total cost:** {money(res.total_cost)} ({num(opt.pallets)} pallet{'' if opt.pallets == 1 else 's'} × {money(opt.price_per_pallet)})",
            f"**Collection:** {format_date(res.collection_date)} from {b.get('origin_city')}",
            f"**Estimated delivery:** {format_date(res.eta)} to {b.get('dest_city')}",
            f"**Goods:** {len(res.items)} product line(s), {num(res.item_cartons)} cartons, "
            f"declared value {money(b.get('declared_value'))}, gross weight {kg(b.get('gross_kg'))}",
        ]
        st.markdown("\n".join(f"- {line}" for line in lines))
        st.caption(res.eta_notes)
        ambers = [f for f in res.findings if f.severity == "Amber"]
        if ambers:
            st.markdown("**Sort these out before collection:**\n" + "\n".join(f"- {f.fix}" for f in ambers))


def next_steps(res: engine.BookingResult) -> None:
    b = res.booking
    steps = []
    blockers = res.red_count + res.data_count
    if blockers:
        steps.append(f"**Fix the {blockers} blocking problem{'s' if blockers != 1 else ''}** listed above, then check again.")
    steps.append(
        f"**Prepare the {abbr('Commercial invoice', 'commercial invoice')}** "
        f"(<a href='{INVOICE_GUIDE}' target='_blank'>GOV.UK guide</a>). Include: seller and buyer names and addresses; "
        f"a description of each item; its {abbr('HS code')}; quantity; unit value and total value; currency (GBP); "
        f"{abbr('Country of origin', 'country of origin')}; {abbr('Net weight', 'net')} and "
        f"{abbr('Gross weight', 'gross')} weights; and the {abbr('Incoterms')} (e.g. DAP or DDP).")
    steps.append(f"**Confirm {abbr('EORI number', 'EORI numbers')}**: your GB EORI (starts with GB) as exporter, "
                 f"and the EU EORI of the importer in {escape(str(b.get('dest_country') or 'the EU'))}.")
    cartons = res.item_cartons if res.item_cartons is not None else b.get("cartons")
    steps.append(f"**Label every carton** with the booking reference and \"carton x of {num(cartons)}\", "
                 "so the count matches what's declared.")
    if b.get("dest_type") == "Warehouse":
        appt = "Confirm" if b.get("appointment") == "Yes" else "Book"
        steps.append(f"**{appt} the delivery appointment** with the receiving warehouse for "
                     f"{format_date(res.eta)}, and share the booking reference.")
    else:
        steps.append(f"**Tell the receiver** to expect delivery around {format_date(res.eta)} and check their opening hours.")
    pallets = b.get("pallets")
    steps.append(f"**Hand over on {format_date(res.collection_date)}**: {num(pallets) if pallets else 'the'} pallet(s), "
                 f"wrapped and labelled, with the invoice and packing list ready at {escape(str(b.get('origin_city') or 'the collection address'))}.")
    st.markdown("\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)), unsafe_allow_html=True)


def render(res: engine.BookingResult, key: str, on_apply: Callable[[dict], None] | None = None,
           show_confirmation: bool = True, confirmed: bool = False) -> None:
    """Full results for one booking: status, findings, carriers, confirmation, next steps."""
    status_banner(res)
    for n in res.notices:
        st.caption(f"⚠️ {n['message']}")
    st.markdown("#### 1. What we found")
    findings(res, key, on_apply)
    st.markdown("#### 2. Carrier recommendation")
    carriers(res)
    if show_confirmation:
        st.markdown("#### 3. Confirmation")
        confirmation(res, confirmed)
        st.markdown("#### 4. What happens next")
        next_steps(res)
