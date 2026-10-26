"""Bridge between the React UI and the Python engine. Pure functions, no Streamlit.

The UI sends small events ({"id", "type", ...}); handle_event() applies them to the
session (chat state via chat_state, file checks via engine) and payload() returns
everything the UI renders, already in plain English. All rule results, statuses,
carrier picks and dates come from engine.py.
"""

from __future__ import annotations

import base64
import copy
import io
import math
import os
from datetime import date
from typing import Any, Callable

import chat_state
import engine
import knowledge
import live_rates
import naming
import planner
import voice
from engine import FIELD_LABELS, format_date, kg, money, num

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_PATH = os.path.join(HERE, "test_bookings.xlsx")
INVOICE_GUIDE = "https://www.gov.uk/guidance/international-trade-paperwork-the-basics"
TARIFF_LOOKUP = "https://www.trade-tariff.service.gov.uk/find_commodity"

WELCOME = ("Hi! I'll help you book a pallet shipment to Europe and check the paperwork before it leaves. "
           "Tell me what you're sending and where, in your own words, or just answer my questions below.")
WELCOME_NO_AI = ("Hi! I'll help you book a pallet shipment to Europe and check the paperwork before it leaves. "
                 "Answer a few quick questions; tap an option or type your answer.")

PLAIN_RULE = {
    "R-01": "Customs code on every product", "R-02": "Declared value matches the products",
    "R-03": "Box maths adds up", "R-04": "Box count matches", "R-05": "Pallets not too heavy",
    "R-06": "No dangerous goods", "R-07": "Total weight is realistic", "R-08": "Warehouse delivery slot",
    "R-09": "Made-in country given", "R-10": "Ready date isn't in the past",
}
FLAGS = {"Germany": "flag-DE", "France": "flag-FR", "Netherlands": "flag-NL", "United Kingdom": "flag-GB"}  # icon keys drawn by the UI
PRIORITY_INFO = {"Cheapest": ("Lowest price", "pound"), "Fastest": ("Quickest delivery", "zap"),
                 "Most reliable": ("Best on-time record", "shield"), "Balanced": ("Good all-round", "scale")}
# (label, placeholder, kind, limit shown under the field)
ITEM_FIELD_INFO = {
    "description": ("What is it?", "e.g. Ceramic coffee mugs", "text", f"Up to {chat_state.MAX_DESCRIPTION} characters"),
    "qty": ("How many units?", "e.g. 1080", "number", "Whole number, 1 or more"),
    "unit_price": ("Price per unit (£)", "e.g. 5", "number", "More than £0, in GBP"),
    "units_per_carton": ("Units in each box", "e.g. 12", "number", "Whole number, 1 or more, no more than the quantity"),
    "cartons": ("Number of boxes", "Leave blank and we'll work it out", "number", "Must equal quantity ÷ units per box"),
    "unit_kg": ("Weight of one unit (kg)", "e.g. 0.5", "number", "More than 0 kg"),
    "hs_code": ("Customs code (HS code)", "6 to 10 digits, e.g. 691200", "text", f"6 to {chat_state.HS_MAX_DIGITS} digits"),
    "coo": ("Where was it made?", "Country of manufacture", "choice", "One of: " + ", ".join(engine.COO_ALLOWED)),
}
MAX_MESSAGE = 1500
MAX_UPLOAD_MB = 15
CARRIER_MAX_KG = {naming.name(c["carrier"]): c["max_kg"] for c in sorted(engine.CARRIERS, key=lambda c: c["max_kg"])}
TOP_KG = max(CARRIER_MAX_KG.values())
_PER_PALLET = ", ".join(f"{n} {kg} kg" for n, kg in CARRIER_MAX_KG.items())


def limit_for(field: str, state: dict) -> str | None:
    """The limit for a booking field, in plain words, worked out from the rate card and the current booking."""
    b, items = state["booking"], state["items"]
    pallets, gross = b.get("pallets"), b.get("gross_kg")
    if field == "pallets":
        need = f" For {kg(gross)} you need at least {math.ceil(gross / TOP_KG)}." if gross else ""
        return f"Whole number, 1 or more. Max weight per pallet: {_PER_PALLET}.{need}"
    if field == "gross_kg":
        if pallets:
            return (f"Up to {num(pallets * TOP_KG)} kg on {_plural(pallets, 'pallet')} "
                    f"({TOP_KG} kg per pallet is the most any service takes; {_PER_PALLET}).")
        return f"Up to {TOP_KG} kg per pallet ({_PER_PALLET}). Include boxes, packaging and pallets."
    if field == "ready_date":
        return f"Today ({format_date(engine.today_london())}) or later."
    if field == "seller":
        return f"Up to {chat_state.MAX_SELLER} characters."
    if field == "cartons":
        total = sum(int(i["cartons"]) for i in items if i.get("cartons")) if items else None
        return f"Must match your products: {num(total)} boxes." if total else "Must match the boxes in your products."
    if field == "declared_value":
        priced = [i for i in items if i.get("qty") and i.get("unit_price")]
        if priced:
            t = sum(i["qty"] * i["unit_price"] for i in priced)
            return f"Within 1% of your products' total ({money(t)}): {money(t * 0.99)} to {money(t * 1.01)}."
        return "Must be within 1% of your products' total value."
    if field in ("dest_city", "dest_country"):
        return "We deliver to Berlin, Frankfurt, Hamburg, Paris, Lyon, Amsterdam and Rotterdam only."
    if field == "origin_city":
        return "We collect from London, Manchester, Birmingham or Leeds only."
    return None


def limits() -> dict:
    """Numbers the UI uses to warn as people type (the server enforces them too)."""
    return {"per_pallet": CARRIER_MAX_KG, "top_kg": TOP_KG, "seller_max": chat_state.MAX_SELLER,
            "description_max": chat_state.MAX_DESCRIPTION, "hs_max": chat_state.HS_MAX_DIGITS,
            "message_max": MAX_MESSAGE, "upload_mb": MAX_UPLOAD_MB, "live_max_pallets": 50, "live_max_kg": 1200}


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


def new_chat(ai_on: bool) -> dict:
    return {"state": chat_state.new_state(), "turns": 0, "last_question": "",
            "messages": [{"role": "assistant", "text": voice.WELCOME_AI if ai_on else voice.WELCOME_GUIDED}]}


def new_session(ai_on: bool = False) -> dict:
    return {"chat": new_chat(ai_on), "file": None, "last_id": None, "flash": None, "ai_on": ai_on}


# ---------------------------------------------------------------------------
# What to ask next (structured, so the UI can show the right control)
# ---------------------------------------------------------------------------


def _opt(value: str, hint: str = "", icon: str = "") -> dict:
    return {"value": value, "label": value, "hint": hint, "icon": icon}


def next_ask(state: dict) -> dict | None:
    """The next question, with the closest valid option first when the seller named a place we don't serve."""
    ask = _next_ask(state)
    if ask and ask["kind"] != "item":
        ask["limit"] = limit_for(ask["field"], state)
        if ask["field"] == "gross_kg" and state["booking"].get("pallets"):
            ask["max"] = state["booking"]["pallets"] * TOP_KG
    sug = (state.get("suggest") or {}).get(ask["field"]) if ask else None
    if ask and sug and ask.get("options"):
        opts = ask["options"]
        hit = next((o for o in opts if o["value"] == sug["value"]), None)
        if hit:
            near = f"Closest to {sug['near']}" + (f" · {sug['km']} km" if sug.get("km") else "")
            ask["options"] = [{**hit, "hint": near, "suggested": True}] + [o for o in opts if o is not hit]
    return ask


def _item_ask(state: dict) -> dict | None:
    for idx, miss in chat_state.missing_item_fields(state):
        label = state["items"][idx].get("description") or f"product {idx + 1}"
        return {"field": "items", "kind": "item", "item_index": idx, "missing": miss,
                "question": f"A few more details about the {label}",
                "hint": "These go on the customs paperwork."}
    return None


def _next_ask(state: dict) -> dict | None:
    b = state["booking"]
    today = engine.today_london()
    for key in chat_state.missing_fields(state):
        if key not in ("dest_country", "dest_city", "items") and _item_ask(state):
            return _item_ask(state)  # product details first: the weight and pallet suggestions need them
        if key == "dest_country":
            return {"field": key, "kind": "choice", "question": "Where's it going?",
                    "options": [_opt(c, ", ".join(cs), FLAGS[c]) for c, cs in engine.DEST_CITIES.items()]}
        if key == "dest_city":
            c = b["dest_country"]
            return {"field": key, "kind": "choice", "question": f"Which city in {c}?",
                    "options": [_opt(x, "", FLAGS[c]) for x in engine.DEST_CITIES[c]]}
        if key == "items":
            return {"field": "items", "kind": "item", "item_index": None, "question": "What are you sending?",
                    "hint": "Add one product at a time. You can add more afterwards.",
                    "missing": list(chat_state.ITEM_ASK_ORDER)}
        if key == "ready_date":
            return {"field": key, "kind": "date", "question": "When will it be ready to collect?",
                    "hint": "The day the pallets can be picked up.", "min": format_date(engine.today_london())}
        if key == "pallets":
            ask = {"field": key, "kind": "number", "question": "How many pallets?", "unit": "pallets",
                   "min": 1, "step": 1, "hint": "A standard pallet is about 120 × 100 cm."}
            plan = planner.suggest_pallets(b, state["items"], today)
            if plan:
                ask["plan"] = plan
                ask["question"] = "How many pallets? Here's what I'd suggest"
                ask["suggestions"] = [{
                    "value": str(o["pallets"]), "label": f"{o['pallets']} pallet{'' if o['pallets'] == 1 else 's'}",
                    "hint": f"{kg(round(o['per_pallet']))} each · {naming.name(o['carrier'])} · {money(o['cost'])}",
                    "suggested": i == 0} for i, o in enumerate([plan["best"]] + plan["alternatives"])]
            return ask
        if key == "gross_kg":
            ask = {"field": key, "kind": "number", "question": "Roughly how heavy is everything?", "unit": "kg",
                   "min": 1, "step": 1, "hint": "Include the boxes, packaging and the pallets themselves."}
            est = planner.estimate_gross(b, state["items"], today)
            if est:
                ask["estimate"] = est
                ask["question"] = "Total weight? Here's my estimate"
                ask["suggestions"] = [{"value": str(est["gross"]), "label": f"{num(est['gross'])} kg",
                                       "hint": f"Goods {kg(est['net'])} + boxes + {est['pallets']} pallet{'' if est['pallets'] == 1 else 's'}",
                                       "suggested": True}]
            return ask
        if key == "dest_type":
            return {"field": key, "kind": "choice", "question": "Is it going to a warehouse or a business?",
                    "options": [_opt("Warehouse", "Distribution or fulfilment centre", "warehouse"),
                                _opt("Business address", "Shop, office or studio", "store")]}
        if key == "appointment":
            return {"field": key, "kind": "choice", "question": "Has the warehouse given you a delivery slot?",
                    "hint": "Most warehouses turn trucks away without one.",
                    "options": [_opt("Yes", "It's booked", "check"), _opt("No", "Not yet", "clock")]}
        if key == "priority":
            return {"field": key, "kind": "choice", "question": "What matters most to you?",
                    "options": [_opt(p, *PRIORITY_INFO[p]) for p in engine.PRIORITIES]}
        if key == "origin_city":
            return {"field": key, "kind": "choice", "question": "Where do we collect from?",
                    "options": [_opt(c, "United Kingdom", FLAGS["United Kingdom"]) for c in engine.ORIGIN_CITIES]}
        if key == "seller":
            return {"field": key, "kind": "text", "question": "What's your business called?",
                    "placeholder": "e.g. Northfield Goods"}
    return _item_ask(state)


def _public_ask(ask: dict | None) -> dict | None:
    """The ask as the UI needs it (no internal planning objects)."""
    if not ask:
        return ask
    return {k: v for k, v in ask.items() if k not in ("plan", "estimate")}


def _ask_text(ask: dict | None) -> str:
    if not ask:
        return ""
    return ask["question"] + ("?" if not ask["question"].endswith("?") else "")


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def _check_chat(chat: dict, review: Callable | None, today: date) -> engine.BookingResult:
    b, items = chat_state.engine_input(chat["state"])
    res = engine.check_booking(b, items, today)
    return review(res) if review else res


def _commit(sess: dict, new_state: dict, changes: list[str], problems: list[str], user_text: str | None,
            review: Callable | None, today: date, hint: str = "", quiet_if_nothing: bool = False,
            answer: str = "", note: str = "") -> None:
    chat = sess["chat"]
    old_state = chat["state"]
    was_complete = chat_state.is_complete(chat["state"])
    old = _check_chat(chat, review, today) if (chat["state"]["items"] or chat["turns"]) else None
    if user_text:
        chat["messages"].append({"role": "user", "text": user_text})
    if changes:
        new_state["confirmed"] = False
    chat["state"] = new_state
    chat["turns"] += 1
    new = _check_chat(chat, review, today)
    diff = chat_state.result_diff(old, new) if old is not None else []
    # One question at a time, matching the control shown under the message, in the assistant's voice.
    nxt = next_ask(new_state)
    ask = voice.question(nxt, new_state) if nxt else (voice.DONE_AGAIN if was_complete else voice.DONE)
    if not changes and not problems:
        text = ("Hmm, I didn't catch any booking details in that one. " if not quiet_if_nothing else "") + ask
    else:
        lead = voice.ack(old_state, new_state, chat["turns"]) if changes else ""
        if hint and not lead:
            lead = hint
        calc = voice.CALCULATED if any("calculated" in c for c in changes) and not was_complete else ""
        text = " ".join(p for p in [lead, calc, " ".join(problems), ask] if p)
    if note:
        text = f"{note} {text}"
    if answer:
        text = f"{answer}\n\n{text}"
    msg = {"role": "assistant", "text": text}
    # Chips only for real changes to something already known, with what they did to the checks.
    edits = [c for c in changes if "→" in c or c.startswith(("Removed item", "Added item")) and len(new_state["items"]) > 1]
    if edits:
        msg["changes"] = edits[:6]
        msg["effects"] = diff[:6]
    chat["messages"].append(msg)
    chat["last_question"] = _ask_text(next_ask(new_state))


def _direct_patch(state: dict, text: str) -> dict | None:
    """Without AI: treat typed text as the answer to the current question."""
    ask = next_ask(state)
    if not ask:
        return None
    if ask["kind"] in ("choice", "number", "text", "date"):
        return {"booking_updates": {ask["field"]: text}}
    if ask["kind"] == "item" and ask["item_index"] is None:
        return {"item_updates": [{"op": "add", "fields": {"description": text}}]}
    return None


def handle_event(sess: dict, ev: dict, *, extractor: Callable | None = None, review: Callable | None = None,
                 today: date | None = None, fetch_live: Callable | None = None) -> dict:
    """Apply one UI event to the session (in place) and return it."""
    today = today or engine.today_london()
    if not isinstance(ev, dict) or ev.get("id") == sess.get("last_id"):
        return sess
    sess["last_id"] = ev.get("id")
    sess["flash"] = None
    sess["download"] = None
    kind = ev.get("type")
    chat = sess["chat"]
    st = chat["state"]

    if kind == "say":
        text = str(ev.get("text") or "").strip()[:MAX_MESSAGE]
        if not text:
            return sess
        steer = voice.question(next_ask(st), st) if next_ask(st) else "Tap any detail of your booking to change it, or ask me about the paperwork."
        cur = next_ask(st)
        pick = next((o for o in (cur or {}).get("suggestions", []) if o.get("suggested")), None)
        if pick and voice.accepts_suggestion(text):
            new, changes, problems = chat_state.apply_patch(st, {"booking_updates": {cur["field"]: pick["value"]}})
            _commit(sess, new, changes, problems, text, review, today)
            return sess
        patch = extractor(text, st, chat["last_question"]) if extractor else None
        if patch is None:  # no AI (or it's down): approved answers by keyword, else treat as an answer
            topic = knowledge.match_topic(text)
            if topic:
                chat["messages"] += [{"role": "user", "text": text},
                                     {"role": "assistant", "text": f"{knowledge.TOPICS[topic]['a']}\n\n{steer}"}]
                return sess
            patch = _direct_patch(st, text)
            if patch is None:
                chat["messages"] += [{"role": "user", "text": text}, {"role": "assistant", "text": (
                    "Sorry, I couldn't reach the assistant just now. " if extractor else "") + steer}]
                return sess
        intent, topic = patch.get("intent", "booking"), patch.get("topic")
        answer = knowledge.TOPICS[topic]["a"] if topic in knowledge.TOPICS else ""
        has_updates = bool(patch.get("booking_updates") or patch.get("item_updates"))
        # Guardrails: the seller only ever sees curated text or our own questions.
        if intent == "off_topic":
            chat["messages"] += [{"role": "user", "text": text},
                                 {"role": "assistant", "text": f"{voice.OFF_TOPIC}\n\n{steer}"}]
            return sess
        if not has_updates and intent in ("question", "greeting"):
            lead = answer or (voice.GREETING if intent == "greeting" else voice.UNKNOWN_QUESTION)
            chat["messages"] += [{"role": "user", "text": text}, {"role": "assistant", "text": f"{lead}\n\n{steer}"}]
            return sess
        dropped = patch.get("dropped") or []
        note = voice.dropped(dropped) if dropped else ""
        new, changes, problems = chat_state.apply_patch(st, patch)
        _commit(sess, new, changes, problems, text, review, today, answer=answer, note=note)
    elif kind in ("answer", "edit"):
        field, value = ev.get("field"), ev.get("value")
        if field not in chat_state.BOOKING_KEYS:
            return sess
        new, changes, problems = chat_state.apply_patch(st, {"booking_updates": {field: value}})
        label = ev.get("label") or str(value)
        user = label if kind == "answer" else f"Change {FIELD_LABELS[field].lower()} to {label}"
        _commit(sess, new, changes, problems, user, review, today)
    elif kind == "item":
        fields = {k: v for k, v in (ev.get("fields") or {}).items() if k in chat_state.ITEM_KEYS and v not in ("", None)}
        idx = ev.get("index")
        if idx is None:
            patch = {"item_updates": [{"op": "add", "fields": fields}]}
            user = f"Add {num(chat_state.parse_number(fields.get('qty')))} × {fields.get('description')}" \
                if fields.get("qty") else f"Add {fields.get('description') or 'a product'}"
        else:
            patch = {"item_updates": [{"op": "update", "match_sku_or_index": int(idx) + 1, "fields": fields}]}
            user = f"Update {st['items'][int(idx)].get('description') or 'product'}" if int(idx) < len(st["items"]) else "Update product"
        new, changes, problems = chat_state.apply_patch(st, patch)
        _commit(sess, new, changes, problems, user, review, today)
    elif kind == "remove_item":
        idx = ev.get("index")
        if isinstance(idx, int) and 0 <= idx < len(st["items"]):
            name = st["items"][idx].get("description") or "product"
            new, changes, problems = chat_state.apply_patch(
                st, {"item_updates": [{"op": "remove", "match_sku_or_index": idx + 1}]})
            _commit(sess, new, changes, problems, f"Remove {name}", review, today)
    elif kind == "fix" and ev.get("scope") == "file":
        _file_fix(sess, ev.get("booking_id"), ev.get("action"))
    elif kind == "fix":
        new, changes, problems = chat_state.apply_fix_action(st, ev.get("action") or {})
        _commit(sess, new, changes, problems, "Fix it for me", review, today, "Done. I've applied that fix.")
    elif kind == "confirm":
        chat["state"]["confirmed"] = True
    elif kind == "reset":
        sess["chat"] = new_chat(sess.get("ai_on", False))
    elif kind == "sample":
        with open(SAMPLE_PATH, "rb") as fh:
            _load_file(sess, [("test_bookings.xlsx", fh.read())], "Example file (test_bookings.xlsx)")
    elif kind == "upload":
        files = []
        for f in ev.get("files") or []:
            try:
                files.append((str(f.get("name") or "file"), base64.b64decode(f.get("b64") or "")))
            except Exception:
                sess["flash"] = "That file couldn't be read. Please try again."
                return sess
        _load_file(sess, files, ", ".join(n for n, _ in files))
    elif kind == "file_undo" and sess.get("file"):
        sess["file"]["edits"].pop(ev.get("booking_id"), None)
    elif kind == "file_clear":
        sess["file"] = None
    elif kind == "live_rates":
        _live_event(sess, ev, review, today, fetch_live or live_rates.quote)
    elif kind == "invoice":
        _invoice_event(sess, ev, review, today)
    return sess



# ---------------------------------------------------------------------------
# Live prices (advisory) and downloads
# ---------------------------------------------------------------------------


def live_signature(res: engine.BookingResult) -> list:
    b = res.booking
    return [b.get("origin_city"), b.get("dest_country"), b.get("dest_city"), b.get("pallets"), b.get("gross_kg")]


def _live_view(res: engine.BookingResult, live: dict | None) -> dict | None:
    """Live quotes only while the route and load are the ones they were fetched for."""
    if not live or live.get("sig") != live_signature(res):
        return None
    out = {k: v for k, v in live.items() if k != "sig"}
    ours = res.total_cost
    if out.get("ok") and ours is not None:
        cheapest = out["quotes"][0]["price"]
        out["ours"] = {"carrier": res.recommendation, "cost": ours, "cost_label": money(ours)}
        out["summary"] = (f"Cheapest live price: {money(cheapest)} ({out['quotes'][0]['service']}). "
                          f"Our fixed-rate pick, {res.recommendation}, is {money(ours)}"
                          + (f", {money(abs(ours - cheapest))} {'more' if ours > cheapest else 'less'}." if ours != cheapest else "."))
    return out


def _result_for(sess: dict, scope: str, booking_id: str | None, review: Callable | None, today: date):
    if scope == "file" and sess.get("file"):
        return next((r for r in file_results(sess, review, today) if r.booking_id == booking_id), None)
    if sess["chat"]["state"]["items"] or sess["chat"]["turns"]:
        return _check_chat(sess["chat"], review, today)
    return None


def _live_event(sess: dict, ev: dict, review: Callable | None, today: date, fetch: Callable) -> None:
    res = _result_for(sess, ev.get("scope", "chat"), ev.get("booking_id"), review, today)
    if res is None:
        return
    b = res.booking
    try:
        data = fetch(b.get("origin_city"), b.get("dest_country"), b.get("dest_city"), int(b.get("pallets") or 0),
                     float(b.get("gross_kg") or 0))
    except Exception:
        data = {"ok": False, "error": "Live prices aren't available right now.", "quotes": []}
    sess.setdefault("live", {})[res.booking_id] = {**data, "sig": live_signature(res)}


def _invoice_event(sess: dict, ev: dict, review: Callable | None, today: date) -> None:
    from ui import export
    res = _result_for(sess, ev.get("scope", "chat"), ev.get("booking_id"), review, today)
    if res is None:
        return
    name = f"commercial-invoice-draft-{'booking' if res.booking_id.startswith('CHAT') else res.booking_id}.xlsx"
    sess["download"] = {"id": ev.get("id"), "name": name, "b64": base64.b64encode(export.invoice_xlsx(res)).decode()}

# ---------------------------------------------------------------------------
# File mode
# ---------------------------------------------------------------------------


def parse_files(files: list[tuple[str, bytes]]) -> tuple[list, list, list]:
    names = [n.lower() for n, _ in files]
    if len(files) == 1 and names[0].endswith((".xlsx", ".xlsm")):
        return engine.load_workbook(io.BytesIO(files[0][1]))
    if len(files) == 2 and all(n.endswith(".csv") for n in names):
        pairs = sorted(files, key=lambda p: 0 if "booking" in p[0].lower() else 1)
        return engine.load_csvs(io.BytesIO(pairs[0][1]), io.BytesIO(pairs[1][1]))
    return [], [], [{"level": "error", "message":
                     "Please choose one Excel file (.xlsx) with Bookings and Items sheets, or two CSV files "
                     "(one for Bookings, one for Items)."}]


def _load_file(sess: dict, files: list[tuple[str, bytes]], label: str) -> None:
    try:
        bookings, items, notices = parse_files(files)
    except Exception as e:  # the loader shouldn't raise; never crash the page
        bookings, items, notices = [], [], [{"level": "error", "message": f"That file couldn't be read ({type(e).__name__})."}]
    sess["file"] = {"label": label, "bookings": bookings, "items": items, "notices": notices, "edits": {}}


def _items_for(data: dict, booking: dict) -> list[dict]:
    key = booking.get("_match_id") or str(booking.get("booking_id") or "").strip().upper()
    return [i for i in data["items"] if str(i.get("booking_id") or "").strip().upper() == key]


def file_results(sess: dict, review: Callable | None, today: date) -> list[engine.BookingResult]:
    data = sess["file"]
    out = engine.check_all(data["bookings"], data["items"], today, data["notices"])
    for i, res in enumerate(out):
        edit = data["edits"].get(res.booking_id)
        if edit:
            res = engine.check_booking(edit["booking"], edit["items"], today)
            res.notices = [{"message": "Changed here: " + "; ".join(edit["log"]) + ". Your file itself is unchanged."}]
        out[i] = review(res) if review else res
    return out


def _file_fix(sess: dict, booking_id: str, action: dict) -> None:
    """File mode changes only the one value the seller clicked, on an in-app copy."""
    data = sess.get("file")
    if not data or not action:
        return
    edit = data["edits"].get(booking_id)
    if edit is None:
        raw = next((b for b in data["bookings"] if b.get("booking_id") == booking_id), None)
        if raw is None:
            return
        edit = {"booking": copy.deepcopy(raw), "items": copy.deepcopy(_items_for(data, raw)), "log": []}
    state = {"booking": edit["booking"], "items": edit["items"], "derived": []}
    new, changes, problems = chat_state.apply_fix_action(state, action, derive=False)
    if changes:
        edit.update(booking=new["booking"], items=new["items"])
        edit["log"] += changes
        data["edits"][booking_id] = edit
    if problems:
        sess["flash"] = " ".join(problems)


# ---------------------------------------------------------------------------
# Serialising results for the UI (plain English lives here, not in React)
# ---------------------------------------------------------------------------


def _plural(n, word: str) -> str:
    return f"{num(n)} {word}{'' if n == 1 else 's'}"


def fix_label(action: dict | None) -> str | None:
    if not action:
        return None
    field, value = action["field"], action["value"]
    shown = (money(value) if field == "declared_value" else kg(value) if field == "gross_kg"
             else str(value) if field in ("hs_code", "ready_date") else num(value))
    label = FIELD_LABELS.get(field, field)
    label = label if label.startswith("HS") else label.lower()
    where = f" for {action['sku']}" if action.get("target") == "item" and action.get("sku") else ""
    return f"Set {label}{where} to {shown}"


def status_view(res: engine.BookingResult) -> dict:
    blockers = res.red_count + res.data_count
    if res.status == "Blocked":
        return {"tone": "red", "label": "Can't ship yet",
                "headline": f"{_plural(blockers, 'problem')} to fix before this can leave",
                "sub": f"{len(res.rules_passed)} of 10 checks passed."}
    if res.status == "Ready with warnings":
        return {"tone": "amber", "label": "OK to ship",
                "headline": f"Sort out {_plural(res.amber_count, 'thing')} before collection",
                "sub": "It can be booked, but these could cause delays or extra charges."}
    return {"tone": "green", "label": "Good to go", "headline": "All 10 checks passed",
            "sub": "Nothing to fix. You can book this as it is."}


def serialise(res: engine.BookingResult, live: dict | None = None) -> dict:
    b = res.booking
    findings = []
    for f in res.findings:
        ai = f.meta.get("ai")
        findings.append({
            "rule": f.rule_id if f.rule_id in engine.RULES else ("Data" if f.severity == "Data" else "Note"),
            "title": PLAIN_RULE.get(f.rule_id, "Missing information" if f.severity == "Data" else "For your information"),
            "severity": f.severity, "message": f.message, "fix": f.fix, "sku": f.sku,
            "why": engine.RULES.get(f.rule_id, {}).get("why") if f.severity != "Advisory" else None,
            "action": f.fix_action, "action_label": fix_label(f.fix_action),
            "ai": ai, "from_ai": f.meta.get("source") == "ai",
        })
    options = []
    for o in res.options:
        options.append({
            "carrier": o.carrier, "service": o.service, "picked": o.carrier == res.recommendation,
            "eligible": o.eligible, "cost": o.cost if o.eligible else (o.cost_if_repalletised or o.cost),
            "cost_label": money(o.cost) if o.eligible or (o.eligible is None and o.cost) else
            (f"{money(o.cost_if_repalletised)} on {o.pallets_needed} pallets" if o.cost_if_repalletised
             else f"{money(o.price_per_pallet)} per pallet"),
            "per_pallet": money(o.price_per_pallet), "transit": o.transit_days, "on_time": o.on_time,
            "max_kg": o.max_kg, "eta": format_date(o.eta) if o.eta else None,
            "excluded": o.excluded_reason.split(": ", 1)[-1] if (o.eligible is False and ": " in o.excluded_reason)
            else (o.excluded_reason or None),
        })
    opt = res.chosen_option
    blocked = res.status == "Blocked"
    pallets = b.get("pallets")
    confirmation = {
        "blocked": blocked,
        "route": f"{b.get('origin_city') or '?'} → {b.get('dest_city') or '?'}, {b.get('dest_country') or '?'}",
        "seller": b.get("seller") or "",
        "carrier": f"{opt.carrier} · road, {opt.transit_days} working days, {opt.on_time}% on time" if opt else None,
        "cost": money(res.total_cost) if res.total_cost is not None else None,
        "cost_detail": (f"{_plural(opt.pallets, 'pallet')} × {money(opt.price_per_pallet)}"
                        if opt and opt.eligible and opt.pallets else
                        (f"if spread over {_plural(opt.pallets_needed, 'pallet')}" if opt and opt.pallets_needed else "")),
        "collection": format_date(res.collection_date) if res.collection_date else None,
        "eta": format_date(res.eta) if res.eta else None,
        "eta_notes": res.eta_notes,
        "goods": f"{len(res.items)} product line{'s' if len(res.items) != 1 else ''} · "
                 f"{num(res.item_cartons) if res.item_cartons is not None else '?'} boxes · "
                 f"{money(b.get('declared_value'))} declared · {kg(b.get('gross_kg'))}",
        "todo": [f.fix for f in res.findings if f.severity in (("Red", "Data") if blocked else ("Amber",))],
    }
    steps = []
    blockers = res.red_count + res.data_count
    if blockers:
        steps.append({"title": f"Fix the {_plural(blockers, 'problem')} above", "body": "Then check again. Nothing is booked until these are sorted."})
    steps += [
        {"title": "Prepare the commercial invoice",
         "body": "Seller and buyer names and addresses; what each product is; its HS code; quantity; unit and total "
                 "value in GBP; country of origin; net and gross weights; and the Incoterms (who pays duty, e.g. DAP or DDP).",
         "link": INVOICE_GUIDE, "link_label": "GOV.UK guide"},
        {"title": "Confirm your EORI numbers",
         "body": f"Your GB EORI (starts with GB) as the exporter, and the EU EORI of the importer in {b.get('dest_country') or 'the EU'}."},
        {"title": "Label every box",
         "body": f"Booking reference and \"box x of {num(res.item_cartons if res.item_cartons is not None else b.get('cartons'))}\", so the count matches what's declared."},
        ({"title": ("Confirm" if b.get("appointment") == "Yes" else "Book") + " the delivery slot",
          "body": f"With the receiving warehouse, for {format_date(res.eta)}. Share the booking reference."}
         if b.get("dest_type") == "Warehouse" else
         {"title": "Tell the receiver", "body": f"Delivery is expected around {format_date(res.eta)}. Check their opening hours."}),
        {"title": f"Hand over on {format_date(res.collection_date)}",
         "body": f"{_plural(pallets, 'pallet') if pallets else 'Pallets'} wrapped and labelled, invoice and packing list ready at "
                 f"{b.get('origin_city') or 'the collection address'}."},
    ]
    return {
        "id": res.booking_id, "status": res.status, "view": status_view(res),
        "counts": {"red": res.red_count, "data": res.data_count, "amber": res.amber_count,
                   "advisory": res.count("Advisory"), "passed": len(res.rules_passed)},
        "rules": [{"id": r, "name": PLAIN_RULE[r], "state": s, "why": engine.RULES[r]["why"]} for r, s in res.rule_status.items()],
        "findings": findings, "options": options, "recommendation": res.recommendation, "reason": res.reason,
        "why_others": res.why_others_lost,
        "load": {"gross": kg(b.get("gross_kg")) if b.get("gross_kg") else None,
                 "pallets": num(pallets) if pallets else None,
                 "per_pallet": kg(res.weight_per_pallet) if res.weight_per_pallet else None,
                 "priority": b.get("priority") if b.get("priority") in engine.PRIORITIES else "Balanced"},
        "confirmation": confirmation, "next_steps": steps,
        "notices": [n["message"] for n in res.notices],
        "invoice": knowledge.invoice_checklist(res),
        "country": knowledge.country_rules(res),
        "live": _live_view(res, live),
        "can_live": bool(b.get("dest_country") in engine.DEST_CITIES and b.get("pallets") and b.get("gross_kg")),
    }


def _booking_rows(state: dict) -> list[dict]:
    b, derived = state["booking"], set(state.get("derived", []))
    missing = set(chat_state.missing_fields(state))
    dest = ", ".join(x for x in (b.get("dest_city"), b.get("dest_country")) if x)
    rows = [
        ("seller", "Your business", b.get("seller"), "text", None),
        ("origin_city", "From", f"{b['origin_city']}, UK" if b.get("origin_city") else None, "choice", engine.ORIGIN_CITIES),
        ("dest_city", "To", dest or None, "choice", [c for cs in engine.DEST_CITIES.values() for c in cs]),
        ("dest_type", "Delivering to", b.get("dest_type"), "choice", engine.DEST_TYPES),
    ]
    if b.get("dest_type") == "Warehouse":
        rows.append(("appointment", "Delivery slot booked", b.get("appointment"), "choice", engine.YES_NO))
    rows += [
        ("ready_date", "Ready on", b.get("ready_date"), "date", None),
        ("priority", "Priority", b.get("priority"), "choice", engine.PRIORITIES),
        ("pallets", "Pallets", num(b["pallets"]) if b.get("pallets") else None, "stepper", None),
        ("gross_kg", "Total weight", kg(b["gross_kg"]) if b.get("gross_kg") else None, "number", None),
        ("cartons", "Boxes", num(b["cartons"]) if b.get("cartons") else None, "number", None),
        ("declared_value", "Declared value", money(b["declared_value"]) if b.get("declared_value") else None, "number", None),
    ]
    out = []
    for key, label, display, kind, options in rows:
        is_missing = key in missing or (key == "dest_city" and ("dest_country" in missing or not b.get("dest_city")))
        out.append({"key": key, "label": label, "display": display, "raw": b.get(key), "kind": kind,
                    "limit": limit_for(key, state),
                    "options": options, "missing": bool(is_missing and not display),
                    "calculated": key in derived})
    return out


def chat_view(sess: dict, review: Callable | None, today: date) -> dict:
    chat = sess["chat"]
    state = chat["state"]
    missing = chat_state.missing_fields(state)
    item_missing = chat_state.missing_item_fields(state)
    total = len([r for r in _booking_rows(state) if r["key"] not in ("cartons", "declared_value")]) + max(1, len(state["items"]))
    left = len([m for m in missing]) + len(item_missing)
    complete = chat_state.is_complete(state)
    started = bool(state["items"]) or chat["turns"] > 0
    res = _check_chat(chat, review, today) if started else None
    return {
        "messages": chat["messages"][-60:],
        "ask": _public_ask(next_ask(state)),
        "rows": _booking_rows(state),
        "items": [{"index": i, **{k: it.get(k) for k in chat_state.ITEM_KEYS}, "calculated_cartons": bool(it.get("_cartons_derived")),
                   "missing": [f for f in chat_state.ITEM_ASK_ORDER if engine.is_blank(it.get(f))]}
                  for i, it in enumerate(state["items"])],
        "progress": {"done": max(0, total - left), "total": total},
        "complete": complete, "confirmed": bool(state.get("confirmed")),
        "result": serialise(res, (sess.get("live") or {}).get(res.booking_id)) if res is not None else None,
    }


def file_view(sess: dict, review: Callable | None, today: date) -> dict | None:
    data = sess.get("file")
    if not data:
        return None
    from ui import export
    results = file_results(sess, review, today) if data["bookings"] else []
    counts = engine.status_counts(results)
    rows = [{"id": r.booking_id, "seller": r.booking.get("seller") or "", "route": export.route(r),
             "status": r.status, "tone": status_view(r)["tone"], "label": status_view(r)["label"],
             "problems": r.red_count + r.data_count, "warnings": r.amber_count,
             "carrier": r.recommendation, "cost": money(r.total_cost) if r.total_cost is not None else "—",
             "eta": format_date(r.eta) if r.eta else "—", "edited": r.booking_id in data["edits"]} for r in results]
    xlsx = base64.b64encode(export.to_xlsx(results)).decode() if results else None
    return {"label": data["label"], "notices": data["notices"], "counts": {"total": len(results), **counts},
            "rows": rows, "results": {r.booking_id: serialise(r, (sess.get("live") or {}).get(r.booking_id)) for r in results},
            "xlsx": xlsx}


def payload(sess: dict, review: Callable | None = None, today: date | None = None) -> dict:
    today = today or engine.today_london()
    return {
        "ack": sess.get("last_id"), "ai": bool(sess.get("ai_on")), "today": format_date(today),
        "download": sess.get("download"),
        # Customer-facing names (Economy/Standard/Express) applied once, to everything the UI shows.
        "flash": sess.get("flash"), "chat": naming.brand(chat_view(sess, review, today)),
        "file": naming.brand(file_view(sess, review, today)),
        "coo_options": engine.COO_ALLOWED, "item_fields": {k: list(v) for k, v in ITEM_FIELD_INFO.items()},
        "limits": limits(),
        "tariff_link": TARIFF_LOOKUP,
    }
