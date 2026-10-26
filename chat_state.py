"""Conversation state for chat booking: pure functions, no Streamlit, no LLM.

The LLM (or the guided form) produces a patch:
    {"booking_updates": {...},
     "item_updates": [{"op": "add|update|remove", "match_sku_or_index": ..., "fields": {...}}],
     "reply_hint": "..."}
apply_patch() validates every value against the allowed values, merges it into the
booking/items, and reports what changed and what needs asking. Rule results always
come from engine.check_booking(); nothing here decides pass/fail.
"""

from __future__ import annotations

import copy
import re
from typing import Any

import engine
import geo
from engine import FIELD_LABELS, is_blank, parse_number

BOOKING_KEYS = ["seller", "origin_city", "origin_country", "dest_city", "dest_country", "dest_type",
                "ready_date", "priority", "pallets", "cartons", "declared_value", "currency", "gross_kg",
                "appointment"]
MAX_SELLER = 100
MAX_DESCRIPTION = 200
HS_MAX_DIGITS = 10

ITEM_KEYS = ["sku", "description", "hs_code", "qty", "unit_price", "units_per_carton", "cartons", "unit_kg", "coo"]
INT_FIELDS = {"pallets", "cartons", "qty", "units_per_carton"}
POSITIVE_FIELDS = {"pallets", "gross_kg", "qty", "unit_price", "units_per_carton", "unit_kg", "declared_value", "cartons"}

QUESTIONS = {
    "dest_country": "Which country is it going to: Germany, France or the Netherlands?",
    "dest_city": "Which city is it going to?",
    "items": "What are you sending? For each product, tell me what it is, how many units and the price per unit.",
    "ready_date": "When will the goods be ready to collect? (DD-MM-YYYY)",
    "pallets": "How many pallets is it?",
    "gross_kg": "What's the total gross weight in kg (goods + packaging + pallets)?",
    "dest_type": "Is it being delivered to a warehouse or a business address (like a shop or office)?",
    "appointment": "Has a delivery appointment been booked with the warehouse? (Yes/No)",
    "priority": "What matters most: cheapest, fastest, most reliable, or a balance of all three?",
    "origin_city": "Where are we collecting from: London, Manchester, Birmingham or Leeds?",
    "seller": "What's the seller (your business) name?",
}
ITEM_QUESTION_WORDS = {
    "description": "what the product is", "qty": "how many units", "unit_price": "the price per unit (£)",
    "hs_code": "the HS code (the 6-10 digit customs commodity code)", "units_per_carton": "how many units per carton",
    "cartons": "how many cartons", "unit_kg": "the weight of one unit (kg)",
    "coo": "the country of origin (where it was made)",
}
# Order to ask in: route and goods first, admin last.
# Route and goods first, then priority, so we can suggest the weight and the pallet count.
ASK_ORDER = ["dest_country", "dest_city", "items", "priority", "ready_date", "gross_kg", "pallets", "dest_type",
             "appointment", "origin_city", "seller"]
ITEM_ASK_ORDER = ["description", "qty", "unit_price", "hs_code", "units_per_carton", "cartons", "unit_kg", "coo"]


def new_state() -> dict:
    return {
        "booking": {"booking_id": "CHAT-1", "origin_country": engine.ORIGIN_COUNTRY, "currency": engine.CURRENCY},
        "items": [],
        "derived": [],  # fields we calculated from the items, e.g. ["cartons", "declared_value"]
        "confirmed": False,
    }


# ---------------------------------------------------------------------------
# Value validation
# ---------------------------------------------------------------------------


def _fmt(v: Any) -> str:
    if isinstance(v, float) and v.is_integer():
        return f"{int(v):,}"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)


def _number(field: str, raw: Any, current: Any) -> tuple[Any, str | None]:
    """Parse a number. Supports relative edits like "+1" / "-2" (the code does the maths)."""
    if isinstance(raw, dict):  # {"add": 1}
        delta = parse_number(raw.get("add", raw.get("by")))
        raw = None if delta is None else (f"+{delta}" if delta >= 0 else str(delta))
    if isinstance(raw, str) and re.fullmatch(r"\s*[+-]\s*\d+(\.\d+)?\s*", raw):
        if current is None:
            return None, f"I don't have a current {FIELD_LABELS[field].lower()} to change yet. What should it be?"
        val = float(current) + float(raw.replace(" ", ""))
    else:
        val = parse_number(raw)
    if val is None:
        return None, f"'{raw}' doesn't look like a number for {FIELD_LABELS[field].lower()}."
    if field in INT_FIELDS:
        if not float(val).is_integer():
            return None, f"{FIELD_LABELS[field]} must be a whole number (got {_fmt(val)})."
        val = int(val)
    if field in POSITIVE_FIELDS and val <= 0:
        return None, f"{FIELD_LABELS[field]} must be more than zero."
    return val, None


def validate_booking_field(field: str, raw: Any, booking: dict) -> tuple[Any, str | None]:
    """Return (clean value, problem). A problem means the value wasn't accepted."""
    if field in ("pallets", "cartons", "declared_value", "gross_kg"):
        return _number(field, raw, booking.get(field))
    if is_blank(raw):
        return None, None
    s = str(raw).strip()
    if field == "seller":
        if len(s) > MAX_SELLER:
            return None, f"Business name can be up to {MAX_SELLER} characters (that one is {len(s)})."
        return s, None
    if field == "origin_country":
        c = engine.canon_country(s)
        if c != engine.ORIGIN_COUNTRY:
            return None, f"We only collect in the United Kingdom, not {s}."
        return c, None
    if field == "origin_city":
        c = engine.canon_origin_city(s)
        if c is None:
            near = geo.nearest_served(s, origin=True)
            if near and near["place_country"] == engine.ORIGIN_COUNTRY:
                return None, (f"We don't collect from {near['place']}. The closest collection city is {near['city']}, "
                              f"about {near['km']} km away. Use {near['city']}, or choose another: "
                              f"{', '.join(engine.ORIGIN_CITIES)}.")
            return None, f"We don't collect from {s}. We collect from {', '.join(engine.ORIGIN_CITIES)}. Which is closest?"
        return c, None
    if field == "dest_country":
        c = engine.canon_country(s)
        if c not in engine.DEST_CITIES:
            near = geo.nearest_countries(s)
            hint = f" The closest we deliver to is {' or '.join('the Netherlands' if n == 'Netherlands' else n for n in near)}." if near else ""
            return None, f"We don't deliver to {s}.{hint} We go to Germany, France or the Netherlands."
        return c, None
    if field == "dest_city":
        c = engine.canon_dest_city(s)
        if c is None:
            near = geo.nearest_served(s)
            if near and near["place_country"] in engine.DEST_CITIES:
                return None, (f"We don't deliver to {near['place']}. The closest city we serve is {near['city']}, "
                              f"about {near['km']} km away. Use {near['city']}, or pick another city in {near['place_country']}.")
            if near:
                return None, (f"{near['place']} is in {near['place_country']}, which we don't deliver to. The closest city "
                              f"we serve is {near['city']} ({near['country']}), about {near['km']} km away.")
            return None, f"We don't deliver to {s}. " + _city_options()
        return c, None
    if field == "dest_type":
        c = engine.canon_dest_type(s)
        if c is None:
            return None, f"Is '{s}' a warehouse or a business address (like a shop or office)?"
        return c, None
    if field == "priority":
        c = engine.canon_priority(s)
        if c is None:
            return None, f"I didn't catch the priority '{s}'. Choose cheapest, fastest, most reliable or balanced."
        return c, None
    if field == "appointment":
        c = engine.canon_yes_no(raw)
        if c is None:
            return None, "Has the delivery appointment been booked? Please answer Yes or No."
        return c, None
    if field == "currency":
        if s.upper() not in ("GBP", "£", "POUNDS", "STERLING"):
            return None, f"Bookings are in GBP only. Please give the values in pounds (I can't convert {s})."
        return "GBP", None
    if field == "ready_date":
        d = engine.parse_date(s)
        if d is None:
            return None, f"I couldn't read '{s}' as a date. Please use DD-MM-YYYY, e.g. 05-11-2026."
        return engine.format_date(d), None
    return s, None


def validate_item_field(field: str, raw: Any, item: dict) -> tuple[Any, str | None]:
    if field in ("qty", "unit_price", "units_per_carton", "cartons", "unit_kg"):
        return _number(field, raw, item.get(field))
    if is_blank(raw):
        return None, None
    if field == "hs_code":
        hs = engine.hs_text(raw)
        if not hs.isdigit():
            return None, f"HS code '{raw}' should be digits only (6 to 10 of them)."
        if len(hs) > HS_MAX_DIGITS:
            return None, f"HS codes have at most {HS_MAX_DIGITS} digits; '{hs}' has {len(hs)}."
        return hs, None  # too short is reported by R-01, not here
    if field == "coo":
        c = engine.canon_country(raw)
        if c in engine.COO_ALLOWED:
            return c, None
        return str(raw).strip(), None  # kept as given; the engine adds an advisory
    if field == "description" and len(str(raw).strip()) > MAX_DESCRIPTION:
        return None, f"Product description can be up to {MAX_DESCRIPTION} characters."
    return str(raw).strip(), None


def _city_options() -> str:
    return "Choose from: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in engine.DEST_CITIES.items()) + "."


# ---------------------------------------------------------------------------
# Applying a patch
# ---------------------------------------------------------------------------


def find_item(items: list[dict], key: Any) -> int | None:
    """Match an item by SKU, item number (1-based, as shown to the seller) or description words."""
    if key is None or not items:
        return None
    if isinstance(key, bool):
        return None
    if isinstance(key, (int, float)) and float(key).is_integer():
        i = int(key) - 1
        return i if 0 <= i < len(items) else None
    s = str(key).strip().lower()
    if re.fullmatch(r"#?\d+", s):
        return find_item(items, int(s.lstrip("#")))
    for i, it in enumerate(items):
        if str(it.get("sku") or "").lower() == s:
            return i
    words = [w.rstrip("s") for w in re.findall(r"[a-z0-9]+", s) if len(w) > 2 and w not in ("the", "all", "and")]
    best, best_score = None, 0
    for i, it in enumerate(items):
        desc = [w.rstrip("s") for w in re.findall(r"[a-z0-9]+", str(it.get("description") or "").lower())]
        score = sum(1 for w in words if w in desc)
        if score > best_score:
            best, best_score = i, score
    return best


def _label(item: dict, idx: int) -> str:
    return item.get("description") or item.get("sku") or f"item {idx + 1}"


def apply_patch(state: dict, patch: dict, derive: bool = True) -> tuple[dict, list[str], list[str]]:
    """Merge a patch into a copy of state. Returns (new_state, changes, problems).

    changes: human-readable diffs ("Pallets 3 → 4").
    problems: values that were not accepted and need asking about.
    """
    st = copy.deepcopy(state)
    b, items = st["booking"], st["items"]
    changes, problems = [], []
    patch = patch if isinstance(patch, dict) else {}

    bu = patch.get("booking_updates") or {}
    if not isinstance(bu, dict):
        bu = {}
    bu = {k: v for k, v in bu.items() if k in BOOKING_KEYS and v is not None}

    # Destination: resolve city/country together so "Lyon" alone switches to France,
    # and "Lyon, Germany" is asked about instead of guessed.
    if "dest_city" in bu or "dest_country" in bu:
        city_raw, ctry_raw = bu.pop("dest_city", None), bu.pop("dest_country", None)
        city, cp = validate_booking_field("dest_city", city_raw, b) if city_raw is not None else (None, None)
        ctry, kp = validate_booking_field("dest_country", ctry_raw, b) if ctry_raw is not None else (None, None)
        problems += [p for p in (cp, kp) if p]
        if cp:  # a place we don't serve: remember the closest one we do, and its country if that's served
            near = geo.nearest_served(str(city_raw))
            if near:
                st.setdefault("suggest", {})["dest_city"] = {"value": near["city"], "near": near["place"], "km": near["km"]}
                if not ctry and not b.get("dest_country") and near["place_country"] in engine.DEST_CITIES:
                    ctry = near["place_country"]
        if kp:
            near_c = geo.nearest_countries(str(ctry_raw))
            if near_c:
                st.setdefault("suggest", {})["dest_country"] = {"value": near_c[0], "near": str(ctry_raw), "km": None}
        if city and ctry and engine.country_for_city(city) != ctry:
            problems.append(f"{city} is in {engine.country_for_city(city)}, not {ctry}. Did you mean {city}, "
                            f"{engine.country_for_city(city)}, or a city in {ctry} "
                            f"({', '.join(engine.DEST_CITIES[ctry])})?")
        elif city:
            _set(b, "dest_city", city, changes)
            _set(b, "dest_country", engine.country_for_city(city), changes)
        elif ctry:
            _set(b, "dest_country", ctry, changes)
            if b.get("dest_city") and engine.country_for_city(b["dest_city"]) != ctry:
                old = b.pop("dest_city")
                changes.append(f"Destination city {old} cleared (it isn't in {ctry})")

    for field, raw in bu.items():
        if field in ("cartons", "declared_value") and field in st["derived"]:
            st["derived"].remove(field)  # the seller stated it, so stop calculating it
        val, prob = validate_booking_field(field, raw, b)
        if prob:
            problems.append(prob)
            if field == "origin_city":
                near = geo.nearest_served(str(raw), origin=True)
                if near:
                    st.setdefault("suggest", {})["origin_city"] = {"value": near["city"], "near": near["place"], "km": near["km"]}
        elif val is not None:
            _set(b, field, val, changes)
            if field == "ready_date":
                d = engine.parse_date(val)
                if d and d < engine.today_london():
                    problems.append(f"{val} is in the past. When will the goods actually be ready?")

    for upd in patch.get("item_updates") or []:
        if not isinstance(upd, dict):
            continue
        op = str(upd.get("op") or "").lower()
        fields = upd.get("fields") if isinstance(upd.get("fields"), dict) else {}
        key = upd.get("match_sku_or_index")
        if op == "add":
            it: dict = {}
            for f, raw in fields.items():
                if f not in ITEM_KEYS or raw is None:
                    continue
                val, prob = validate_item_field(f, raw, it)
                if prob:
                    problems.append(prob)
                elif val is not None:
                    it[f] = val
            if not it.get("description") and not it.get("sku"):
                problems.append("I couldn't tell which product to add. What is it?")
                continue
            it.setdefault("sku", _next_sku(items))
            items.append(it)
            changes.append(f"Added item: {_label(it, len(items) - 1)}")
        elif op in ("update", "remove"):
            idx = find_item(items, key)
            if idx is None:
                problems.append(f"I couldn't find the item '{key}'. Your items are: "
                                + (", ".join(f"#{i + 1} {_label(x, i)}" for i, x in enumerate(items)) or "none yet") + ".")
                continue
            if op == "remove":
                gone = items.pop(idx)
                changes.append(f"Removed item: {_label(gone, idx)}")
                continue
            it = items[idx]
            for f, raw in fields.items():
                if f not in ITEM_KEYS or raw is None:
                    continue
                if f == "cartons":
                    it.pop("_cartons_derived", None)
                val, prob = validate_item_field(f, raw, it)
                if prob:
                    problems.append(prob)
                elif val is not None and it.get(f) != val:
                    old = it.get(f)
                    it[f] = val
                    changes.append(f"{_label(it, idx)}: {FIELD_LABELS[f].lower()} "
                                   + (f"{_fmt(old)} → {_fmt(val)}" if old is not None else f"set to {_fmt(val)}"))

    if derive:
        _derive(st, changes)
    return st, changes, problems


def _set(b: dict, field: str, val: Any, changes: list[str]) -> None:
    old = b.get(field)
    if old == val:
        return
    b[field] = val
    changes.append(f"{FIELD_LABELS[field]} {_fmt(old)} → {_fmt(val)}" if old not in (None, "")
                   else f"{FIELD_LABELS[field]} set to {_fmt(val)}")


def _next_sku(items: list[dict]) -> str:
    n = len(items) + 1
    used = {str(i.get("sku")) for i in items}
    while f"ITEM-{n}" in used:
        n += 1
    return f"ITEM-{n}"


def _derive(st: dict, changes: list[str]) -> None:
    """Fill fields the seller didn't state from the items (marked as calculated).

    Item cartons = quantity ÷ units per carton (only when whole). Booking cartons and
    declared value = item totals. Seller-stated values are never overwritten.
    """
    b, items, derived = st["booking"], st["items"], st["derived"]
    for i, it in enumerate(items):
        q, u = it.get("qty"), it.get("units_per_carton")
        if (it.get("cartons") is None or it.get("_cartons_derived")) and q and u and float(q / u).is_integer():
            new = int(q / u)
            if it.get("cartons") != new:
                it["cartons"] = new
                it["_cartons_derived"] = True
                changes.append(f"{_label(it, i)}: calculated {new:,} cartons ({_fmt(q)} units ÷ {_fmt(u)} per carton)")
    if items and all(it.get("cartons") is not None for it in items):
        total = int(sum(it["cartons"] for it in items))
        if b.get("cartons") is None or "cartons" in derived:
            if b.get("cartons") != total:
                _set(b, "cartons", total, changes)
                changes[-1] += " (calculated from the items)"
            if "cartons" not in derived:
                derived.append("cartons")
    if items and all(it.get("qty") is not None and it.get("unit_price") is not None for it in items):
        total = round(sum(it["qty"] * it["unit_price"] for it in items), 2)
        if b.get("declared_value") is None or "declared_value" in derived:
            if b.get("declared_value") != total:
                _set(b, "declared_value", total, changes)
                changes[-1] += " (calculated from the items)"
            if "declared_value" not in derived:
                derived.append("declared_value")


# ---------------------------------------------------------------------------
# What's missing and what to ask
# ---------------------------------------------------------------------------


def missing_fields(state: dict) -> list[str]:
    """Missing required booking fields, in the order we ask about them."""
    b, items = state["booking"], state["items"]
    out = []
    for key in ASK_ORDER:
        if key == "items":
            if not items:
                out.append("items")
            continue
        if key == "appointment" and b.get("dest_type") != "Warehouse":
            continue  # only warehouses need a delivery appointment
        if key == "dest_city" and not b.get("dest_country"):
            continue  # asked together with the country
        if is_blank(b.get(key)):
            out.append(key)
    return out


def missing_item_fields(state: dict) -> list[tuple[int, list[str]]]:
    out = []
    for i, it in enumerate(state["items"]):
        miss = [f for f in ITEM_ASK_ORDER if is_blank(it.get(f))]
        if miss:
            out.append((i, miss))
    return out


def is_complete(state: dict) -> bool:
    return not missing_fields(state) and not missing_item_fields(state) and bool(state["items"])


def questions(state: dict, limit: int = 2) -> list[str]:
    """The next one or two things to ask, in plain words. Never asks for known values."""
    b = state["booking"]
    qs = []
    for key in missing_fields(state):
        if key == "dest_country" and not b.get("dest_city"):
            qs.append(QUESTIONS["dest_country"])
        elif key == "dest_city":
            qs.append(f"Which city in {b['dest_country']}: {', '.join(engine.DEST_CITIES[b['dest_country']])}?")
        else:
            qs.append(QUESTIONS[key])
        if len(qs) >= limit:
            return qs
    for idx, miss in missing_item_fields(state):
        it = state["items"][idx]
        words = [ITEM_QUESTION_WORDS[f] for f in miss[:3]]
        what = " and ".join([", ".join(words[:-1]), words[-1]] if len(words) > 1 else words)
        qs.append(f"For the {_label(it, idx)}: {what}?")
        if len(qs) >= limit:
            break
    return qs


def build_reply(state: dict, changes: list[str], problems: list[str], hint: str | None = None) -> str:
    """Compose the assistant message in code, so it only ever asks for what's missing."""
    parts = []
    if hint and "?" not in hint and len(hint) < 240:
        parts.append(hint.strip())
    if problems:
        parts.append(" ".join(problems))
    qs = questions(state, limit=1 if problems else 2)
    if qs:
        parts.append(" ".join(qs))
    elif not problems:
        parts.append("That's everything I need. Here are the checks and the carrier I'd pick. "
                     "If it all looks right, press **Confirm booking**.")
    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Engine input and result diffs
# ---------------------------------------------------------------------------


def engine_input(state: dict) -> tuple[dict, list[dict]]:
    b = {k: v for k, v in state["booking"].items()}
    items = [{k: v for k, v in it.items() if not k.startswith("_")} for it in state["items"]]
    return b, items


def result_diff(old, new) -> list[str]:
    """Plain-English changes between two BookingResults (from the engine)."""
    if old is None or new is None:
        return []
    out = []
    for r in engine.RULE_IDS:
        a, b = old.rule_status.get(r), new.rule_status.get(r)
        if a != b:
            if b == "Pass":
                out.append(f"{r} now passes")
            elif a == "Pass":
                out.append(f"{r} now {'fails' if b in ('Red', 'Amber') else 'needs data'} ({b})")
            else:
                out.append(f"{r} {a} → {b}")
    if old.recommendation != new.recommendation and new.recommendation and old.recommendation:
        out.append(f"Carrier: {old.recommendation} → {new.recommendation}")
    if old.total_cost != new.total_cost and new.total_cost is not None and old.total_cost is not None:
        out.append(f"Cost {engine.money(old.total_cost)} → {engine.money(new.total_cost)}")
    if old.eta != new.eta and new.eta and old.eta:
        out.append(f"Delivery {engine.format_date(old.eta)} → {engine.format_date(new.eta)}")
    if old.status != new.status:
        out.append(f"Status {old.status} → {new.status}")
    return out


def apply_fix_action(state: dict, action: dict, derive: bool = True) -> tuple[dict, list[str], list[str]]:
    """Turn an engine fix_action into a patch and apply it. derive=False changes only that one value."""
    if not action:
        return state, [], []
    if action.get("target") == "booking":
        patch = {"booking_updates": {action["field"]: action["value"]}}
    else:
        key = action.get("sku") or (action.get("index", 0) + 1)
        patch = {"item_updates": [{"op": "update", "match_sku_or_index": key,
                                   "fields": {action["field"]: action["value"]}}]}
    return apply_patch(state, patch, derive=derive)
