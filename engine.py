"""Rules engine and carrier recommender for UK -> EU pallet bookings.

This module is the single source of truth for rule results (R-01 to R-10),
booking status, carrier choice and ETAs. The UI and the LLM only display or
explain what it returns; they never decide a result themselves.

Public interface
    load_workbook(file) -> (bookings, items, notices)
    load_csvs(bookings_file, items_file) -> (bookings, items, notices)
    check_all(bookings, items, today=None, notices=None) -> list[BookingResult]
    check_booking(booking, items, today=None) -> BookingResult
"""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterable

try:  # Holiday-aware ETAs; weekends-only if the library is missing.
    import holidays as _holidays
except Exception:  # pragma: no cover
    _holidays = None

# ---------------------------------------------------------------------------
# Fixed reference data (from the case brief)
# ---------------------------------------------------------------------------

ORIGIN_COUNTRY = "United Kingdom"
ORIGIN_CITIES = ["London", "Manchester", "Birmingham", "Leeds"]
DEST_CITIES = {
    "Germany": ["Berlin", "Frankfurt", "Hamburg"],
    "France": ["Paris", "Lyon"],
    "Netherlands": ["Amsterdam", "Rotterdam"],
}
DEST_TYPES = ["Warehouse", "Business address"]
PRIORITIES = ["Cheapest", "Fastest", "Most reliable", "Balanced"]
YES_NO = ["Yes", "No"]
CURRENCY = "GBP"
COO_ALLOWED = ["United Kingdom", "China", "India", "Vietnam", "Turkey", "Germany"]

CARRIERS = [
    {"carrier": "Carrier A", "service": "Road economy",
     "rates": {"Germany": 180, "France": 170, "Netherlands": 160},
     "transit_days": 5, "on_time": 92, "max_kg": 500},
    {"carrier": "Carrier B", "service": "Road standard",
     "rates": {"Germany": 220, "France": 210, "Netherlands": 200},
     "transit_days": 3, "on_time": 95, "max_kg": 750},
    {"carrier": "Carrier C", "service": "Road express",
     "rates": {"Germany": 340, "France": 330, "Netherlands": 320},
     "transit_days": 2, "on_time": 98, "max_kg": 400},
]

HOLIDAY_CODES = {"United Kingdom": ("GB", "ENG"), "Germany": ("DE", None),
                 "France": ("FR", None), "Netherlands": ("NL", None)}

RULES = {
    "R-01": {"name": "HS code present (6+ digits)", "severity": "Red",
             "why": "Customs classify every item by its HS code. A missing or short code stops the export declaration."},
    "R-02": {"name": "Declared value matches items", "severity": "Red",
             "why": "The declared value must match the commercial invoice. A mismatch triggers customs queries, holds or penalties."},
    "R-03": {"name": "Units per carton x cartons = quantity", "severity": "Red",
             "why": "If cartons don't add up to the quantity, the packing list is wrong and the goods can't be reconciled at the border."},
    "R-04": {"name": "Booking cartons = item cartons", "severity": "Red",
             "why": "The carrier counts cartons at collection and delivery. A mismatch means a disputed or refused handover."},
    "R-05": {"name": "Weight per pallet within carrier limit", "severity": "Red",
             "why": "Each carrier has a maximum weight per pallet. Overweight pallets are refused at collection."},
    "R-06": {"name": "No restricted dangerous goods", "severity": "Red",
             "why": "Lithium batteries, aerosols and flammable liquids need a dangerous-goods (ADR) service. These road services can't carry them."},
    "R-07": {"name": "Gross weight covers item weight", "severity": "Amber",
             "why": "Gross weight (goods + packaging) can't be less than the goods alone. Wrong weights cause re-weigh charges and customs queries."},
    "R-08": {"name": "Warehouse delivery has an appointment", "severity": "Amber",
             "why": "Most EU warehouses turn away trucks without a booked delivery slot, which adds a failed-delivery fee and delay."},
    "R-09": {"name": "Country of origin given", "severity": "Amber",
             "why": "Country of origin decides duty and whether UK-EU preferential (zero) tariff applies."},
    "R-10": {"name": "Ready date not in the past", "severity": "Amber",
             "why": "A ready date in the past can't be collected on, so the collection date and delivery estimate will move."},
}
RULE_IDS = list(RULES)

REQUIRED_BOOKING_FIELDS = [
    "seller", "origin_city", "dest_country", "dest_city", "dest_type", "ready_date",
    "priority", "pallets", "gross_kg", "appointment",
]
# Booking cartons and declared value can be calculated from the items.
DERIVABLE_BOOKING_FIELDS = ["cartons", "declared_value"]
REQUIRED_ITEM_FIELDS = ["description", "hs_code", "qty", "unit_price",
                        "units_per_carton", "cartons", "unit_kg", "coo"]

FIELD_LABELS = {
    "booking_id": "Booking ID", "seller": "Seller name", "origin_city": "Origin city",
    "origin_country": "Origin country", "dest_city": "Destination city",
    "dest_country": "Destination country", "dest_type": "Destination type",
    "ready_date": "Ready to ship date", "priority": "Seller priority",
    "pallets": "Pallets", "cartons": "Cartons", "declared_value": "Total declared value",
    "currency": "Currency", "gross_kg": "Total gross weight (kg)",
    "appointment": "Delivery appointment booked",
    "sku": "SKU", "description": "Description", "hs_code": "HS code", "qty": "Quantity",
    "unit_price": "Unit price", "units_per_carton": "Units per carton",
    "unit_kg": "Unit weight (kg)", "coo": "Country of origin",
}

SEVERITY_ORDER = {"Red": 0, "Data": 1, "Amber": 2, "Advisory": 3}

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    rule_id: str
    severity: str  # Red / Amber / Data / Advisory
    message: str
    fix: str
    sku: str | None = None
    # Optional machine-readable fix, used by "Apply this fix" buttons:
    # {"target": "booking"|"item", "field": ..., "value": ..., "sku"/"index": ...}
    fix_action: dict | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class CarrierOption:
    carrier: str
    service: str
    price_per_pallet: float
    pallets: int | None
    cost: float | None
    transit_days: int
    on_time: int
    max_kg: int
    eligible: bool | None  # None = weight unknown
    excluded_reason: str = ""
    pallets_needed: int | None = None
    cost_if_repalletised: float | None = None
    eta: date | None = None


@dataclass
class BookingResult:
    booking_id: str
    booking: dict
    items: list[dict]
    findings: list[Finding]
    status: str  # Blocked / Ready with warnings / Ready
    rules_passed: list[str]
    rule_status: dict[str, str]
    options: list[CarrierOption]
    recommendation: str | None
    reason: str
    runner_up: str | None
    why_others_lost: list[str]
    weight_per_pallet: float | None
    collection_date: date | None
    eta: date | None
    eta_notes: str
    items_total: float | None
    net_kg: float | None
    item_cartons: float | None
    notices: list[dict] = field(default_factory=list)

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f.severity == severity)

    @property
    def red_count(self) -> int:
        return self.count("Red")

    @property
    def amber_count(self) -> int:
        return self.count("Amber")

    @property
    def data_count(self) -> int:
        return self.count("Data")

    @property
    def chosen_option(self) -> CarrierOption | None:
        return next((o for o in self.options if o.carrier == self.recommendation), None)

    @property
    def total_cost(self) -> float | None:
        opt = self.chosen_option
        if opt is None:
            return None
        return opt.cost if opt.eligible else (opt.cost_if_repalletised or opt.cost)


# ---------------------------------------------------------------------------
# Value parsing (tolerant: Excel numbers, text, chat strings)
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"^[£$€]?\s*-?[\d,]*\.?\d+\s*(kg|kgs|gbp|units?|pallets?|cartons?)?$", re.I)


def is_blank(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return isinstance(v, str) and v.strip() == ""


def parse_number(v: Any) -> float | None:
    """Return a float, or None if blank or not a number."""
    if is_blank(v) or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not _NUM_RE.match(s):
        return None
    s = re.sub(r"[£$€,\s]|kg|kgs|gbp|units?|pallets?|cartons?", "", s, flags=re.I)
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(v: Any) -> date | None:
    """Parse a date. Text is always read as DD-MM-YYYY (05-11-2026 = 5 Nov)."""
    if is_blank(v):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if hasattr(v, "to_pydatetime"):  # pandas Timestamp
        try:
            return v.to_pydatetime().date()
        except Exception:
            return None
    if isinstance(v, (int, float)) and 20000 < float(v) < 80000:  # Excel serial
        return date(1899, 12, 30) + timedelta(days=int(v))
    s = str(v).strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$", s)  # ISO from datetimes
    if m:
        y, mo, d = (int(x) for x in m.groups())
    else:
        m = re.match(r"^(\d{1,2})[-/. ](\d{1,2})[-/. ](\d{2,4})$", s)
        if not m:
            return None
        d, mo, y = (int(x) for x in m.groups())
        if y < 100:
            y += 2000
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def format_date(d: date | None) -> str:
    return d.strftime("%d-%m-%Y") if d else "—"


def hs_text(v: Any) -> str:
    """HS code as text without losing digits that Excel kept."""
    if is_blank(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    return re.sub(r"[\s.]", "", str(v).strip())


def money(v: float | None) -> str:
    return "—" if v is None else f"£{v:,.2f}"


def kg(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.0f} kg" if float(v).is_integer() else f"{v:,.1f} kg"


def num(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"


def _canon(value: Any, allowed: Iterable[str], synonyms: dict[str, str] | None = None) -> str | None:
    """Match a value to an allowed option, case-insensitively."""
    if is_blank(value):
        return None
    s = re.sub(r"^(?:(?:to|at|in|from)\s+)?(?:a|an|the|our|my|their)\s+", "", str(value).strip().lower())
    key = re.sub(r"[^a-z]", "", s)
    for a in allowed:
        if re.sub(r"[^a-z]", "", a.lower()) == key:
            return a
    if synonyms and key in synonyms:
        return synonyms[key]
    return None


COUNTRY_SYNONYMS = {"uk": "United Kingdom", "gb": "United Kingdom", "greatbritain": "United Kingdom",
                    "england": "United Kingdom", "unitedkingdom": "United Kingdom",
                    "de": "Germany", "deutschland": "Germany", "fr": "France",
                    "nl": "Netherlands", "holland": "Netherlands", "thenetherlands": "Netherlands",
                    "cn": "China", "prc": "China", "in": "India", "vn": "Vietnam", "vietnam": "Vietnam",
                    "tr": "Turkey", "turkiye": "Turkey"}
CITY_SYNONYMS = {"frankfurtammain": "Frankfurt", "frankfort": "Frankfurt", "frankfurtmain": "Frankfurt"}
DEST_TYPE_SYNONYMS = {"business": "Business address", "businessaddress": "Business address",
                      "shop": "Business address", "office": "Business address", "store": "Business address",
                      "warehouse": "Warehouse", "dc": "Warehouse", "distributioncentre": "Warehouse",
                      "fulfilmentcentre": "Warehouse", "fulfillmentcenter": "Warehouse"}
PRIORITY_SYNONYMS = {"cheap": "Cheapest", "cheapest": "Cheapest", "lowestcost": "Cheapest",
                     "fast": "Fastest", "fastest": "Fastest", "quickest": "Fastest", "express": "Fastest",
                     "reliable": "Most reliable", "mostreliable": "Most reliable", "reliability": "Most reliable",
                     "balanced": "Balanced", "balance": "Balanced", "bestvalue": "Balanced"}
YES_NO_SYNONYMS = {"y": "Yes", "yes": "Yes", "true": "Yes", "booked": "Yes",
                   "n": "No", "no": "No", "false": "No", "notbooked": "No"}


def canon_country(v: Any) -> str | None:
    return _canon(v, [ORIGIN_COUNTRY, *DEST_CITIES, *COO_ALLOWED], COUNTRY_SYNONYMS)


def canon_dest_city(v: Any) -> str | None:
    return _canon(v, [c for cs in DEST_CITIES.values() for c in cs], CITY_SYNONYMS)


def canon_origin_city(v: Any) -> str | None:
    return _canon(v, ORIGIN_CITIES)


def canon_dest_type(v: Any) -> str | None:
    return _canon(v, DEST_TYPES, DEST_TYPE_SYNONYMS)


def canon_priority(v: Any) -> str | None:
    return _canon(v, PRIORITIES, PRIORITY_SYNONYMS)


def canon_yes_no(v: Any) -> str | None:
    if isinstance(v, bool):
        return "Yes" if v else "No"
    return _canon(v, YES_NO, YES_NO_SYNONYMS)


def country_for_city(city: str | None) -> str | None:
    for country, cities in DEST_CITIES.items():
        if city in cities:
            return country
    return None


# ---------------------------------------------------------------------------
# R-06 keyword screen
# ---------------------------------------------------------------------------

# Clear dangerous-goods phrases -> Red. (phrase pattern, category)
DG_RED = [
    (r"lithium(?:[- ]ion)?", "lithium battery"), (r"li[- ]?ion", "lithium battery"),
    (r"li[- ]?po(?:ly)?\b", "lithium battery"), (r"power ?banks?", "lithium battery"),
    (r"rechargeable", "lithium battery"), (r"bluetooth", "lithium battery"),
    (r"e[- ]?cig(?:arette)?s?", "lithium battery"), (r"vapes?\b", "lithium battery"),
    (r"vape pens?", "lithium battery"), (r"e[- ]?liquids?", "flammable liquid"),
    (r"aerosols?", "aerosol"), (r"spray paints?", "aerosol"), (r"hair ?sprays?", "aerosol"),
    (r"deodorant sprays?", "aerosol"), (r"spray deodorants?", "aerosol"), (r"body sprays?", "aerosol"),
    (r"spray cans?", "aerosol"), (r"compressed (?:air|gas)", "aerosol"), (r"gas canisters?", "aerosol"),
    (r"butane", "flammable liquid"), (r"lighter fluid", "flammable liquid"), (r"lighter gas", "aerosol"),
    (r"perfumes?", "flammable liquid"), (r"colognes?", "flammable liquid"),
    (r"eau de (?:parfum|toilette|cologne)", "flammable liquid"), (r"nail (?:polish|varnish)", "flammable liquid"),
    (r"nail polish remover", "flammable liquid"), (r"acetone", "flammable liquid"),
    (r"hand sanit[iy][sz]ers?", "flammable liquid"), (r"hand gel", "flammable liquid"),
    (r"solvents?", "flammable liquid"), (r"paint thinners?", "flammable liquid"), (r"thinners", "flammable liquid"),
    (r"white spirit", "flammable liquid"), (r"methylated spirits?", "flammable liquid"),
    (r"isopropyl", "flammable liquid"), (r"rubbing alcohol", "flammable liquid"), (r"ethanol", "flammable liquid"),
    (r"petrol", "flammable liquid"), (r"kerosene", "flammable liquid"), (r"lamp oil", "flammable liquid"),
    (r"flammable", "flammable liquid"), (r"inflammable", "flammable liquid"),
]
# Ambiguous words -> Advisory, for a person (or the AI reviewer) to confirm.
DG_AMBIGUOUS = [
    (r"batter(?:y|ies)", "lithium battery"), (r"wireless", "lithium battery"), (r"cordless", "lithium battery"),
    (r"usb", "lithium battery"), (r"electric(?:al)?", "lithium battery"), (r"smart ?watch", "lithium battery"),
    (r"headphones?|earbuds?|speakers?", "lithium battery"), (r"\bled\b", "lithium battery"),
    (r"sprays?", "aerosol"), (r"mists?", "aerosol"), (r"cleaning|cleaners?|detergents?|degreasers?", "flammable liquid"),
    (r"cosmetics?|make-?up", "flammable liquid"), (r"fragrances?|scented", "flammable liquid"),
    (r"essential oils?|oils?\b", "flammable liquid"), (r"alcohol", "flammable liquid"),
    (r"gin|vodka|whisk(?:e)?y|rum|spirits|liqueurs?", "flammable liquid"), (r"paints?|varnish|lacquer", "flammable liquid"),
    (r"glue|adhesive", "flammable liquid"), (r"gas\b", "aerosol"), (r"matches", "flammable liquid"),
    (r"lighters?", "flammable liquid"),
]
# Phrases that negate a hazard ("battery-free", "non-aerosol", "alcohol free", "no battery").
_NEGATION_RE = re.compile(
    r"\b(?:non[- ]?|no |without |zero[- ])[a-z-]+"
    r"|\b(?:batter(?:y|ies)|alcohol|aerosol|solvent|lithium|fragrance|perfume|propellant|gas)[- ]free\b"
    r"|\b[a-z]+-free\b", re.I)


def dg_screen(description: str | None) -> tuple[str, str, str] | None:
    """Keyword screen for R-06.

    Returns (level, phrase, category) where level is "red" or "ambiguous", or None.
    """
    if is_blank(description):
        return None
    text = " " + str(description).lower() + " "
    text = _NEGATION_RE.sub(" ", text)
    is_candle = "candle" in text
    for pattern, cat in DG_RED:
        m = re.search(r"\b(?:" + pattern + r")\b", text)
        if m:
            return ("red", m.group(0).strip(), cat)
    for pattern, cat in DG_AMBIGUOUS:
        m = re.search(r"\b(?:" + pattern + r")\b", text)
        if m:
            phrase = m.group(0).strip()
            if is_candle and phrase in ("fragrance", "fragrances", "scented", "oil", "oils"):
                continue  # candles are not on the restricted list
            return ("ambiguous", phrase, cat)
    return None


# ---------------------------------------------------------------------------
# Loading files
# ---------------------------------------------------------------------------

BOOKING_ALIASES = [
    ("booking_id", ["bookingid", "bookingref", "booking"]),
    ("seller", ["sellername", "seller"]),
    ("origin_city", ["origincity", "collectioncity", "fromcity"]),
    ("origin_country", ["origincountry", "fromcountry"]),
    ("dest_city", ["destinationcity", "destcity", "tocity"]),
    ("dest_country", ["destinationcountry", "destcountry", "tocountry"]),
    ("dest_type", ["destinationtype", "desttype", "deliverytype"]),
    ("ready_date", ["readytoshipdate", "readytoship", "readydate", "shipdate"]),
    ("priority", ["sellerpriority", "priority"]),
    ("pallets", ["pallets", "palletcount", "noofpallets", "numberofpallets"]),
    ("cartons", ["cartons", "totalcartons", "cartoncount"]),
    ("declared_value", ["totaldeclaredvalue", "declaredvalue", "totalvalue"]),
    ("currency", ["currency"]),
    ("gross_kg", ["totalgrossweight", "grossweight", "grosskg"]),
    ("appointment", ["deliveryappointmentbooked", "deliveryappointment", "appointmentbooked", "appointment"]),
]
ITEM_ALIASES = [
    ("booking_id", ["bookingid", "bookingref", "booking"]),
    ("sku", ["sku", "itemcode", "productcode"]),
    ("description", ["description", "itemdescription"]),
    ("hs_code", ["hscode", "hs", "commoditycode", "tariffcode"]),
    ("qty", ["quantityunits", "quantity", "qty"]),
    ("unit_price", ["unitprice", "price"]),
    ("units_per_carton", ["unitspercarton", "unitspercartons", "percarton"]),
    ("cartons", ["cartons", "cartoncount"]),
    ("unit_kg", ["unitweight", "unitkg", "weightperunit"]),
    ("coo", ["countryoforigin", "origincountry", "coo", "origin"]),
]
BOOKING_NUMERIC = ["pallets", "cartons", "declared_value", "gross_kg"]
ITEM_NUMERIC = ["qty", "unit_price", "units_per_carton", "cartons", "unit_kg"]


def _norm_header(h: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(h or "").lower())


def _map_headers(headers: list[Any], aliases: list[tuple[str, list[str]]]) -> dict[int, str]:
    """Map column index -> field key. Exact alias matches win over prefix matches."""
    normed = [_norm_header(h) for h in headers]
    mapping: dict[int, str] = {}
    used: set[str] = set()
    for exact in (True, False):
        for key, names in aliases:
            if key in used:
                continue
            for i, h in enumerate(normed):
                if i in mapping or not h:
                    continue
                if any((h == n) if exact else h.startswith(n) for n in names):
                    mapping[i] = key
                    used.add(key)
                    break
    return mapping


def _rows_to_records(rows: list[list[Any]], aliases, numeric: list[str], sheet: str,
                     notices: list[dict]) -> list[dict]:
    header_idx = None
    for i, row in enumerate(rows[:30]):
        if any(_norm_header(c) == "bookingid" for c in row):
            header_idx = i
            break
    if header_idx is None:
        notices.append({"level": "error", "message": f"{sheet}: couldn't find a header row containing 'Booking ID'."})
        return []
    mapping = _map_headers(rows[header_idx], aliases)
    missing = [FIELD_LABELS[k] for k, _ in aliases if k not in mapping.values()]
    if missing:
        notices.append({"level": "warning",
                        "message": f"{sheet}: missing column(s) {', '.join(missing)}. Checks that need them will report missing data."})
    records = []
    for r_i, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if all(is_blank(c) for c in row):
            continue
        rec: dict[str, Any] = {"_row": r_i, "_parse_errors": []}
        for c_i, key in mapping.items():
            val = row[c_i] if c_i < len(row) else None
            if isinstance(val, str):
                val = val.strip()
            if key == "hs_code":
                val = hs_text(val)
            elif key in numeric and not is_blank(val):
                parsed = parse_number(val)
                if parsed is None:
                    rec["_parse_errors"].append((key, str(val)))
                val = parsed
            elif key == "booking_id" and not is_blank(val):
                val = str(int(val)) if isinstance(val, float) and val.is_integer() else str(val).strip()
            rec[key] = None if is_blank(val) else val
        # Rows with values but nothing we recognise (e.g. a notes line) are skipped.
        if all(is_blank(rec.get(k)) for k, _ in aliases):
            continue
        records.append(rec)
    return records


def _finalise(bookings: list[dict], items: list[dict], notices: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    seen: dict[str, int] = {}
    for b in bookings:
        bid = b.get("booking_id")
        if is_blank(bid):
            b["booking_id"] = f"Row {b['_row']} (no ID)"
            notices.append({"level": "warning", "booking_id": b["booking_id"],
                            "message": f"Bookings row {b['_row']} has no Booking ID; checked as '{b['booking_id']}'."})
            continue
        key = str(bid).strip().upper()
        b["_match_id"] = key
        if key in seen:
            seen[key] += 1
            b["booking_id"] = f"{bid} (duplicate, row {b['_row']})"
            notices.append({"level": "warning", "booking_id": b["booking_id"],
                            "message": f"Booking ID {bid} appears more than once (row {b['_row']}). Both copies were checked against the same items; give each booking a unique ID."})
        else:
            seen[key] = 1
    booking_keys = {b.get("_match_id") for b in bookings if b.get("_match_id")}
    orphans: dict[str, list[str]] = {}
    for it in items:
        bid = it.get("booking_id")
        if is_blank(bid):
            notices.append({"level": "warning",
                            "message": f"Items row {it['_row']} (SKU {it.get('sku') or '—'}) has no Booking ID, so it wasn't checked."})
        elif str(bid).strip().upper() not in booking_keys:
            orphans.setdefault(str(bid), []).append(str(it.get("sku") or f"row {it['_row']}"))
    for bid, skus in orphans.items():
        notices.append({"level": "warning",
                        "message": f"Orphan item(s): {', '.join(skus)} reference Booking ID {bid}, which isn't on the Bookings sheet."})
    return bookings, items, notices


def load_workbook(file) -> tuple[list[dict], list[dict], list[dict]]:
    """Read an .xlsx with Bookings and Items sheets (judges' template layout).

    `file` may be a path or a file-like object. Never raises on bad content;
    problems come back as notices.
    """
    import openpyxl

    notices: list[dict] = []
    try:
        wb = openpyxl.load_workbook(file, data_only=True, read_only=True)
    except Exception as e:
        return [], [], [{"level": "error", "message": f"Couldn't open the file as an Excel workbook ({type(e).__name__})."}]
    sheets = {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}
    wb.close()

    def has_header(rows, word):
        return any(any(_norm_header(c) == word for c in row) for row in rows[:30])

    b_name = next((n for n in sheets if "booking" in n.lower()), None) or \
        next((n for n, r in sheets.items() if has_header(r, "bookingid") and not has_header(r, "sku")), None)
    i_name = next((n for n in sheets if "item" in n.lower()), None) or \
        next((n for n, r in sheets.items() if has_header(r, "sku")), None)
    if not b_name:
        notices.append({"level": "error", "message": "No Bookings sheet found (expected a sheet named 'Bookings')."})
    if not i_name:
        notices.append({"level": "error", "message": "No Items sheet found (expected a sheet named 'Items')."})
    bookings = _rows_to_records(sheets[b_name], BOOKING_ALIASES, BOOKING_NUMERIC, "Bookings", notices) if b_name else []
    items = _rows_to_records(sheets[i_name], ITEM_ALIASES, ITEM_NUMERIC, "Items", notices) if i_name else []
    return _finalise(bookings, items, notices)


def _read_csv(file) -> list[list[Any]]:
    data = file.read() if hasattr(file, "read") else open(file, "rb").read()
    if isinstance(data, bytes):
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                data = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    return [row for row in csv.reader(io.StringIO(data))]


def load_csvs(bookings_file, items_file) -> tuple[list[dict], list[dict], list[dict]]:
    """Same as load_workbook, for a Bookings CSV and an Items CSV."""
    notices: list[dict] = []
    try:
        b_rows, i_rows = _read_csv(bookings_file), _read_csv(items_file)
    except Exception as e:
        return [], [], [{"level": "error", "message": f"Couldn't read the CSV files ({type(e).__name__})."}]
    # If the two files were uploaded the other way round, swap them.
    def has_sku(rows):
        return any(any(_norm_header(c) == "sku" for c in row) for row in rows[:30])
    if has_sku(b_rows) and not has_sku(i_rows):
        b_rows, i_rows = i_rows, b_rows
    bookings = _rows_to_records(b_rows, BOOKING_ALIASES, BOOKING_NUMERIC, "Bookings", notices)
    items = _rows_to_records(i_rows, ITEM_ALIASES, ITEM_NUMERIC, "Items", notices)
    return _finalise(bookings, items, notices)


# ---------------------------------------------------------------------------
# Dates and ETA
# ---------------------------------------------------------------------------


def today_london() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/London")).date()
    except Exception:  # pragma: no cover - tzdata missing
        return datetime.utcnow().date()


_holiday_cache: dict[tuple[str, int], Any] = {}


def _holiday_name(country: str, d: date) -> str | None:
    if _holidays is None or country not in HOLIDAY_CODES:
        return None
    code, subdiv = HOLIDAY_CODES[country]
    key = (country, d.year)
    if key not in _holiday_cache:
        try:
            _holiday_cache[key] = _holidays.country_holidays(code, subdiv=subdiv, years=d.year)
        except Exception:
            _holiday_cache[key] = {}
    return _holiday_cache[key].get(d)


def _is_working_day(d: date, countries: list[str]) -> bool:
    return d.weekday() < 5 and not any(_holiday_name(c, d) for c in countries)


def _skipped_holidays(start: date, end: date, countries: list[str]) -> list[str]:
    out = []
    d = start
    while d <= end:
        for c in countries:
            name = _holiday_name(c, d)
            if name and d.weekday() < 5:
                out.append(f"{name} ({c}, {format_date(d)})")
        d += timedelta(days=1)
    return out


def collection_and_eta(ready: date | None, today: date, transit_days: int,
                       dest_country: str | None) -> tuple[date | None, date | None, str]:
    if ready is None:
        return None, None, "No valid ready date, so no collection date or delivery estimate yet."
    notes = []
    start = ready
    if ready < today:
        start = today
        notes.append(f"The ready date {format_date(ready)} is in the past, so we assumed collection from today ({format_date(today)}).")
    collection = start
    while not _is_working_day(collection, ["United Kingdom"]):
        collection += timedelta(days=1)
    if collection != start:
        notes.append(f"Collection moved to the next UK working day, {format_date(collection)}.")
    countries = ["United Kingdom"] + ([dest_country] if dest_country in DEST_CITIES else [])
    eta, n = collection, 0
    while n < transit_days:
        eta += timedelta(days=1)
        if _is_working_day(eta, countries):
            n += 1
    hol = _skipped_holidays(collection, eta, countries)
    base = (f"Estimate = collection date + {transit_days} working days in transit "
            f"(Mon–Fri{', skipping UK and ' + dest_country + ' public holidays' if dest_country in DEST_CITIES else ''}).")
    notes.insert(0, base)
    if hol:
        notes.append("Holidays skipped: " + "; ".join(hol) + ".")
    if _holidays is None:
        notes.append("Public holidays not checked (weekends only).")
    return collection, eta, " ".join(notes)


# ---------------------------------------------------------------------------
# Carrier recommendation
# ---------------------------------------------------------------------------


def _rank_key(priority: str, cost: float):
    def key(o: CarrierOption):
        c = cost(o)
        if priority == "Cheapest":
            return (c, -o.on_time, o.transit_days)
        if priority == "Fastest":
            return (o.transit_days, -o.on_time, c)
        return (-o.on_time, c, o.transit_days)  # Most reliable
    return key


def _regrets(cands: list[CarrierOption], cost) -> dict[str, tuple[float, float]]:
    """Minimax regret: per metric, regret = (value - best) / (worst - best)."""
    metrics = [
        (lambda o: cost(o), False),          # lower is better
        (lambda o: o.transit_days, False),
        (lambda o: o.on_time, True),         # higher is better
    ]
    out = {}
    for o in cands:
        regs = []
        for f, higher_better in metrics:
            vals = [f(x) for x in cands]
            best, worst = (max(vals), min(vals)) if higher_better else (min(vals), max(vals))
            regs.append(0.0 if best == worst else abs(f(o) - best) / abs(worst - best))
        out[o.carrier] = (max(regs), sum(regs))
    return out


def _pick(priority: str, cands: list[CarrierOption], cost) -> list[CarrierOption]:
    """Return candidates in rank order for the priority."""
    if priority == "Balanced":
        regs = _regrets(cands, cost)
        return sorted(cands, key=lambda o: (round(regs[o.carrier][0], 9), round(regs[o.carrier][1], 9), cost(o)))
    return sorted(cands, key=_rank_key(priority, cost))


def recommend(gross_kg: float | None, pallets: float | None, dest_country: str | None,
              priority: str | None, ready: date | None, today: date) -> dict:
    """Filter carriers by weight per pallet, then rank by the seller's priority.

    Resolves the R-05 loop: eligibility is decided by weight per pallet first,
    and the pick is made only from eligible carriers. If none is eligible, each
    carrier gets the pallet count it would need, and the pick is made on those.
    """
    out = {"options": [], "recommendation": None, "reason": "", "runner_up": None,
           "why_others_lost": [], "weight_per_pallet": None, "none_fit": False}
    if dest_country not in DEST_CITIES:
        out["reason"] = "No carrier options: the destination country isn't one we ship to (Germany, France or Netherlands)."
        return out
    prio = priority if priority in PRIORITIES else "Balanced"
    pallets_ok = pallets is not None and pallets > 0 and float(pallets).is_integer()
    p = int(pallets) if pallets_ok else None
    wpp = (gross_kg / p) if (gross_kg is not None and gross_kg > 0 and p) else None
    out["weight_per_pallet"] = wpp

    opts = []
    for c in CARRIERS:
        price = c["rates"][dest_country]
        o = CarrierOption(carrier=c["carrier"], service=c["service"], price_per_pallet=price,
                          pallets=p, cost=(price * p if p else None), transit_days=c["transit_days"],
                          on_time=c["on_time"], max_kg=c["max_kg"], eligible=None)
        if gross_kg is not None and gross_kg > 0:
            o.pallets_needed = max(1, math.ceil(gross_kg / c["max_kg"] - 1e-9))
        if wpp is not None:
            o.eligible = wpp <= c["max_kg"] + 1e-9
            if not o.eligible:
                o.excluded_reason = (f"{c['carrier']} excluded: {kg(wpp)} per pallet exceeds its "
                                     f"{c['max_kg']} kg limit.")
                o.cost_if_repalletised = price * o.pallets_needed
        elif gross_kg is not None and gross_kg > 0:  # pallets missing/invalid
            o.eligible = False
            o.excluded_reason = "Pallet count missing or not a whole number, so weight per pallet can't be checked."
            o.cost_if_repalletised = price * o.pallets_needed
        else:
            o.excluded_reason = "Gross weight unknown, so the weight limit can't be checked yet."
        o.eta = collection_and_eta(ready, today, o.transit_days, dest_country)[1]
        opts.append(o)
    out["options"] = opts

    eligible = [o for o in opts if o.eligible]
    if eligible:
        cands, cost = eligible, (lambda o: o.cost if o.cost is not None else o.price_per_pallet)
    elif all(o.pallets_needed for o in opts):
        out["none_fit"] = True
        cands, cost = opts, (lambda o: o.cost_if_repalletised)
    else:  # weight unknown: rank on price per pallet only, provisionally
        cands, cost = opts, (lambda o: o.cost if o.cost is not None else o.price_per_pallet)

    ranked = _pick(prio, cands, cost)
    win = ranked[0]
    out["recommendation"] = win.carrier
    out["runner_up"] = ranked[1].carrier if len(ranked) > 1 else None

    def desc(o):
        c = cost(o)
        n = o.pallets_needed
        pal = f" on {n} pallet{'s' if n != 1 else ''}" if out["none_fit"] else ""
        return f"{money(c)}{pal}, {o.transit_days} days, {o.on_time}% on time"

    others = [o for o in opts if o is not win]
    prio_note = "" if priority in PRIORITIES else " (no valid priority given, so we used Balanced)"
    if prio == "Cheapest":
        reason = f"{win.carrier} is the cheapest option that can carry this load at {desc(win)}"
    elif prio == "Fastest":
        reason = f"{win.carrier} is the fastest option that can carry this load: {desc(win)}"
    elif prio == "Most reliable":
        reason = f"{win.carrier} has the best on-time record among carriers that can take this load: {desc(win)}"
    else:
        if len(cands) >= 2:
            reason = (f"{win.carrier} is the balanced choice: it is never the priciest, slowest or least reliable "
                      f"of the options that fit ({desc(win)})")
        else:
            reason = f"{win.carrier} is the only carrier that can take this load ({desc(win)})"
    if eligible and len(eligible) < len(opts):
        excl = [o for o in opts if not o.eligible]
        reason += ". " + " ".join(o.excluded_reason for o in excl).rstrip(".")
    if out["none_fit"]:
        lead = (f"No carrier can take {kg(wpp)} per pallet as booked, so this assumes the pallets each carrier would need. "
                if wpp else "The pallet count is missing, so this assumes the fewest pallets each carrier would need. ")
        reason = lead + reason
    if gross_kg is None or gross_kg <= 0:
        reason += ". Provisional: we can't check weight limits until the gross weight is known"
    out["reason"] = reason + prio_note + "."

    why = []
    for o in others:
        if eligible and not o.eligible:
            why.append(o.excluded_reason)
            continue
        if prio == "Balanced":
            regs = _regrets(cands, cost)
            worst = []
            vals_cost = [cost(x) for x in cands]
            if cost(o) == max(vals_cost):
                worst.append("the most expensive")
            if o.transit_days == max(x.transit_days for x in cands):
                worst.append("the slowest")
            if o.on_time == min(x.on_time for x in cands):
                worst.append("the least reliable")
            tail = f"it is {' and '.join(worst)}" if worst else "it trades off worse overall"
            why.append(f"{o.carrier} ({desc(o)}): {tail}.")
        elif prio == "Cheapest":
            why.append(f"{o.carrier} costs {money(cost(o))}, {money(cost(o) - cost(win))} more.")
        elif prio == "Fastest":
            if o.transit_days > win.transit_days:
                why.append(f"{o.carrier} takes {o.transit_days} days, {o.transit_days - win.transit_days} more.")
            else:
                why.append(f"{o.carrier} is as fast but loses on the tie-breaker ({desc(o)}).")
        else:
            why.append(f"{o.carrier} is on time {o.on_time}% of the time vs {win.on_time}%.")
    out["why_others_lost"] = why
    return out


# ---------------------------------------------------------------------------
# Rule checks
# ---------------------------------------------------------------------------


def _item_label(it: dict, idx: int) -> str:
    sku = it.get("sku")
    return f"SKU {sku}" if not is_blank(sku) else f"Item {idx + 1}"


def normalise_booking(raw: dict) -> dict:
    b = dict(raw)
    for k in BOOKING_NUMERIC:
        if k in b and not isinstance(b[k], (int, float)) and not is_blank(b[k]):
            parsed = parse_number(b[k])
            if parsed is None:
                b.setdefault("_parse_errors", []).append((k, str(b[k])))
            b[k] = parsed
    return b


def normalise_item(raw: dict) -> dict:
    it = dict(raw)
    it["hs_code"] = hs_text(it.get("hs_code"))
    for k in ITEM_NUMERIC:
        if k in it and not isinstance(it[k], (int, float)) and not is_blank(it[k]):
            parsed = parse_number(it[k])
            if parsed is None:
                it.setdefault("_parse_errors", []).append((k, str(it[k])))
            it[k] = parsed
    return it


def check_booking(booking: dict, items: list[dict], today: date | None = None) -> BookingResult:
    """Run R-01 to R-10 and the carrier recommendation for one booking."""
    today = today or today_london()
    b = normalise_booking(booking or {})
    its = [normalise_item(i) for i in (items or [])]
    F: list[Finding] = []
    bid = str(b.get("booking_id") or "New booking")

    def add(rule, sev, msg, fix, sku=None, action=None, **meta):
        F.append(Finding(rule, sev, msg, fix, sku, action, meta))

    # --- Data checks on booking-level values --------------------------------
    for key, raw in b.get("_parse_errors", []):
        add("DATA", "Data", f"{FIELD_LABELS.get(key, key)} '{raw}' isn't a number.",
            f"Enter {FIELD_LABELS.get(key, key).lower()} as a plain number.")
    origin_country = canon_country(b.get("origin_country")) if not is_blank(b.get("origin_country")) else ORIGIN_COUNTRY
    if origin_country != ORIGIN_COUNTRY:
        add("DATA", "Data", f"Origin country '{b.get('origin_country')}' isn't supported; we only collect in the United Kingdom.",
            "Set origin country to United Kingdom.")
    oc = canon_origin_city(b.get("origin_city"))
    if is_blank(b.get("origin_city")):
        add("DATA", "Data", "Origin city is missing.", f"Choose one of: {', '.join(ORIGIN_CITIES)}.")
    elif oc is None:
        add("DATA", "Data", f"We don't collect from '{b.get('origin_city')}'.",
            f"Choose one of: {', '.join(ORIGIN_CITIES)}.")
    dest_country = canon_country(b.get("dest_country"))
    dest_city = canon_dest_city(b.get("dest_city"))
    if dest_country not in DEST_CITIES:
        if is_blank(b.get("dest_country")):
            # A known city implies the country.
            dest_country = country_for_city(dest_city)
            if dest_country is None:
                add("DATA", "Data", "Destination country is missing.",
                    "Choose Germany, France or Netherlands.")
        else:
            add("DATA", "Data", f"We don't ship to '{b.get('dest_country')}'.",
                "Choose Germany, France or Netherlands.")
            dest_country = None
    if dest_country in DEST_CITIES:
        if is_blank(b.get("dest_city")):
            add("DATA", "Data", "Destination city is missing.",
                f"Choose one of: {', '.join(DEST_CITIES[dest_country])}.")
        elif dest_city not in DEST_CITIES[dest_country]:
            other = country_for_city(dest_city)
            hint = f" ({dest_city} is in {other})" if other else ""
            add("DATA", "Data", f"'{b.get('dest_city')}' isn't a {dest_country} destination we serve{hint}.",
                f"Choose one of: {', '.join(DEST_CITIES[dest_country])}.")
    dest_type = canon_dest_type(b.get("dest_type"))
    if dest_type is None:
        add("DATA", "Data", "Destination type is missing or not recognised." if is_blank(b.get("dest_type"))
            else f"Destination type '{b.get('dest_type')}' isn't recognised.",
            "Choose Warehouse or Business address.")
    priority = canon_priority(b.get("priority"))
    if priority is None:
        add("ADVICE", "Advisory", "No valid seller priority, so the carrier was picked as Balanced.",
            f"Choose one of: {', '.join(PRIORITIES)}.")
    currency = b.get("currency")
    if not is_blank(currency) and str(currency).strip().upper() != CURRENCY:
        add("DATA", "Data", f"Currency is {currency}; bookings must be in GBP.",
            "Convert the values to GBP and set currency to GBP.")
    if is_blank(b.get("seller")):
        add("DATA", "Data", "Seller name is missing.", "Add the seller's (exporter's) name.")
    appointment = canon_yes_no(b.get("appointment"))

    if not its:
        add("R-04", "Data", "This booking has no item lines.",
            "Add the item lines (SKU, description, HS code, quantity, price, cartons, weight, origin) for this booking.")
    for idx, it in enumerate(its):
        for key, raw in it.get("_parse_errors", []):
            add("DATA", "Data", f"{_item_label(it, idx)}: {FIELD_LABELS.get(key, key)} '{raw}' isn't a number.",
                f"Enter {FIELD_LABELS.get(key, key).lower()} as a plain number.", sku=it.get("sku"))

    # --- R-01 HS code ------------------------------------------------------
    for idx, it in enumerate(its):
        hs, lab = it["hs_code"], _item_label(it, idx)
        if not hs:
            add("R-01", "Red", f"{lab} has no HS code.",
                "Add the 6-to-10-digit commodity code (look it up on the GOV.UK Trade Tariff).", sku=it.get("sku"))
        elif not hs.isdigit():
            add("R-01", "Red", f"{lab}: HS code '{hs}' contains characters other than digits.",
                "Enter digits only, at least 6.", sku=it.get("sku"))
        elif len(hs) < 6:
            note = ""
            if len(hs) == 5:
                note = (f" It may have lost a leading zero in Excel (chapters 01–09); if so it should be 0{hs}. "
                        "Format the column as Text so the zero stays.")
            add("R-01", "Red", f"{lab}: HS code {hs} has only {len(hs)} digits; at least 6 are needed.",
                f"Enter the full code with at least 6 digits.{note}", sku=it.get("sku"),
                action=({"target": "item", "index": idx, "sku": it.get("sku"), "field": "hs_code", "value": "0" + hs}
                        if len(hs) == 5 else None))

    # --- R-02 declared value ---------------------------------------------
    priced = [it for it in its if it.get("qty") is not None and it.get("unit_price") is not None]
    items_total = round(sum(it["qty"] * it["unit_price"] for it in priced), 2) if priced else None
    unpriced = [it for it in its if it not in priced]
    declared = b.get("declared_value")
    if its and unpriced:
        add("R-02", "Data", f"Can't total the item values: {len(unpriced)} item(s) are missing quantity or unit price "
            f"({', '.join(_item_label(i, its.index(i)) for i in unpriced)}).",
            "Fill in quantity and unit price for every item.")
    elif its and items_total is not None:
        if declared is None:
            add("R-02", "Red", f"No total declared value; the items total {money(items_total)}.",
                f"Set total declared value to {money(items_total)}.",
                action={"target": "booking", "field": "declared_value", "value": items_total})
        elif items_total == 0:
            add("R-02", "Data", "Items total £0, so the declared value can't be checked.", "Check unit prices.")
        else:
            gap = abs(declared - items_total) / items_total
            if gap > 0.01 + 1e-12:
                add("R-02", "Red",
                    f"Declared {money(declared)} but the items total {money(items_total)} "
                    f"({gap:.1%} gap; up to 1% is allowed).",
                    f"Change total declared value to {money(items_total)}, or correct the item quantities/prices.",
                    action={"target": "booking", "field": "declared_value", "value": items_total},
                    gap=gap)

    # --- R-03 units per carton x cartons = quantity ------------------------
    for idx, it in enumerate(its):
        lab, q, u, c = _item_label(it, idx), it.get("qty"), it.get("units_per_carton"), it.get("cartons")
        if None in (q, u, c):
            miss = [FIELD_LABELS[k].lower() for k, v in (("qty", q), ("units_per_carton", u), ("cartons", c)) if v is None]
            add("R-03", "Data", f"{lab}: can't check cartons, {' and '.join(miss)} missing.",
                f"Fill in {', '.join(miss)}.", sku=it.get("sku"))
            continue
        if abs(u * c - q) > 1e-9:
            whole = u > 0 and abs(q / u - round(q / u)) < 1e-9
            alt = (f"or change cartons to {num(q / u)}" if whole else
                   f"(changing cartons would need {q / u:.2f} cartons, not a whole number, so check units per carton)")
            add("R-03", "Red",
                f"{lab}: {num(u)} units per carton × {num(c)} cartons = {num(u * c)} units, but quantity is {num(q)}.",
                f"Change quantity to {num(u * c)} {alt}.", sku=it.get("sku"),
                action=({"target": "item", "index": idx, "sku": it.get("sku"), "field": "cartons", "value": q / u}
                        if whole else {"target": "item", "index": idx, "sku": it.get("sku"), "field": "qty", "value": u * c}))

    # --- R-04 booking cartons = item cartons -----------------------------
    carton_vals = [it.get("cartons") for it in its]
    item_cartons = sum(c for c in carton_vals if c is not None) if its and None not in carton_vals else None
    b_cartons = b.get("cartons")
    if its and item_cartons is not None:
        if b_cartons is None:
            add("R-04", "Red", f"No booking carton total; the items add up to {num(item_cartons)} cartons.",
                f"Set booking cartons to {num(item_cartons)}.",
                action={"target": "booking", "field": "cartons", "value": item_cartons})
        elif abs(b_cartons - item_cartons) > 1e-9:
            add("R-04", "Red",
                f"Booking says {num(b_cartons)} cartons but the items add up to {num(item_cartons)} "
                f"({num(abs(b_cartons - item_cartons))} {'more' if b_cartons > item_cartons else 'fewer'}).",
                f"Change booking cartons to {num(item_cartons)}, or correct the item carton counts.",
                action={"target": "booking", "field": "cartons", "value": item_cartons})
    elif its:
        add("R-04", "Data", "Can't total item cartons: some items have no carton count.",
            "Fill in cartons for every item.")

    # --- R-05 weight per pallet (with carrier choice) ----------------------
    ready = parse_date(b.get("ready_date"))
    gross, pallets = b.get("gross_kg"), b.get("pallets")
    rec = recommend(gross, pallets, dest_country, priority, ready, today)
    wpp = rec["weight_per_pallet"]
    if gross is None or gross <= 0:
        add("R-05", "Data", "Total gross weight is missing, so the weight-per-pallet limit can't be checked.",
            "Enter the total gross weight in kg (goods + packaging + pallets).")
    elif pallets is None or pallets <= 0 or not float(pallets).is_integer():
        need = {o.carrier: o.pallets_needed for o in rec["options"]}
        add("R-05", "Red",
            "Pallet count is missing or zero." if not pallets else f"Pallet count {num(pallets)} isn't a whole number.",
            "Enter the number of pallets. For " + kg(gross) + " you need at least "
            + (f"{min(need.values())} pallet{'s' if min(need.values()) != 1 else ''} with any carrier."
               if len(set(need.values())) == 1 else ", ".join(f"{n} for {c}" for c, n in need.items()) + "."),
            action=({"target": "booking", "field": "pallets", "value": need.get(rec["recommendation"])}
                    if rec["recommendation"] and need.get(rec["recommendation"]) else None))
    elif rec["none_fit"]:
        lines = [f"{o.carrier} needs {o.pallets_needed} pallets ({money(o.cost_if_repalletised)})" for o in rec["options"]]
        best = next(o for o in rec["options"] if o.carrier == rec["recommendation"])
        add("R-05", "Red",
            f"{kg(gross)} on {num(pallets)} pallets is {kg(wpp)} per pallet, over every carrier's limit "
            f"(highest is 750 kg, Carrier B).",
            f"Spread the load over more pallets: {'; '.join(lines)}. Recommended: {best.pallets_needed} pallets with {best.carrier}.",
            action={"target": "booking", "field": "pallets", "value": best.pallets_needed}, wpp=wpp)
    # (When some carriers fit, R-05 passes for the recommended carrier; exclusions show in the comparison.)

    # --- R-06 dangerous goods ----------------------------------------------
    for idx, it in enumerate(its):
        hit = dg_screen(it.get("description"))
        if not hit:
            continue
        level, phrase, cat = hit
        lab = _item_label(it, idx)
        if level == "red":
            add("R-06", "Red", f"{lab} '{it.get('description')}' looks like a restricted {cat} (found '{phrase}').",
                "Remove this item from the shipment, or ship it separately with a dangerous-goods (ADR) service.",
                sku=it.get("sku"), phrase=phrase, category=cat, source="keyword")
        else:
            add("R-06", "Advisory",
                f"{lab} '{it.get('description')}' mentions '{phrase}', which might mean a {cat}.",
                f"Check whether it contains a {cat}. If it does, remove it from this shipment.",
                sku=it.get("sku"), phrase=phrase, category=cat, source="keyword", ambiguous=True,
                description=it.get("description"))

    # --- R-07 gross >= net ---------------------------------------------------
    weighed = [it for it in its if it.get("unit_kg") is not None and it.get("qty") is not None]
    net_kg = round(sum(it["unit_kg"] * it["qty"] for it in weighed), 3) if weighed else None
    if its and len(weighed) < len(its):
        add("R-07", "Data", "Can't total the item weights: some items have no unit weight or quantity.",
            "Fill in unit weight (kg) and quantity for every item.")
    elif its and gross is not None and net_kg is not None and gross + 1e-9 < net_kg:
        add("R-07", "Amber",
            f"Gross weight {kg(gross)} is {kg(net_kg - gross)} less than the goods alone ({kg(net_kg)}).",
            f"Re-weigh and raise total gross weight to at least {kg(net_kg)} plus packaging and pallets.",
            action={"target": "booking", "field": "gross_kg", "value": math.ceil(net_kg)})

    # --- R-08 warehouse appointment -----------------------------------------
    if dest_type == "Warehouse" and appointment != "Yes":
        add("R-08", "Amber",
            "Delivery is to a warehouse but no delivery appointment is booked." if appointment == "No" or is_blank(b.get("appointment"))
            else f"Delivery is to a warehouse and the appointment value '{b.get('appointment')}' isn't Yes.",
            "Book a delivery slot with the receiving warehouse, then mark the appointment as booked (Yes).")

    # --- R-09 country of origin --------------------------------------------
    for idx, it in enumerate(its):
        coo = it.get("coo")
        if is_blank(coo):
            add("R-09", "Amber", f"{_item_label(it, idx)} has no country of origin.",
                "Add where the goods were made (not where they ship from), e.g. China or United Kingdom.",
                sku=it.get("sku"))
        elif canon_country(coo) not in COO_ALLOWED:
            add("ADVICE", "Advisory",
                f"{_item_label(it, idx)}: country of origin '{coo}' isn't in the template's list "
                f"({', '.join(COO_ALLOWED)}).", "Double-check the country of origin.", sku=it.get("sku"))

    # --- R-10 ready date -----------------------------------------------------
    if ready is None:
        add("R-10", "Data",
            "Ready-to-ship date is missing." if is_blank(b.get("ready_date"))
            else f"Ready-to-ship date '{b.get('ready_date')}' isn't a valid DD-MM-YYYY date.",
            "Enter the date the goods will be ready, as DD-MM-YYYY.")
    elif ready < today:
        add("R-10", "Amber", f"Ready date {format_date(ready)} is in the past (today is {format_date(today)}).",
            "Change the ready-to-ship date to today or a future date.",
            action={"target": "booking", "field": "ready_date", "value": format_date(today)})

    # --- Status and collection/ETA -------------------------------------------
    status, rule_status, rules_passed = _status(F)

    chosen = next((o for o in rec["options"] if o.carrier == rec["recommendation"]), None)
    collection, eta, eta_notes = (collection_and_eta(ready, today, chosen.transit_days, dest_country)
                                  if chosen else (None, None, "No carrier yet, so no delivery estimate."))

    canon = dict(b)
    canon.update({"origin_country": origin_country or b.get("origin_country"),
                  "origin_city": oc or b.get("origin_city"), "dest_country": dest_country or b.get("dest_country"),
                  "dest_city": dest_city or b.get("dest_city"), "dest_type": dest_type or b.get("dest_type"),
                  "priority": priority or b.get("priority"), "appointment": appointment or b.get("appointment"),
                  "currency": b.get("currency") or CURRENCY, "ready_date": format_date(ready) if ready else b.get("ready_date")})

    return BookingResult(
        booking_id=bid, booking=canon, items=its, findings=F, status=status, rules_passed=rules_passed,
        rule_status=rule_status, options=rec["options"], recommendation=rec["recommendation"],
        reason=rec["reason"], runner_up=rec["runner_up"], why_others_lost=rec["why_others_lost"],
        weight_per_pallet=wpp, collection_date=collection, eta=eta, eta_notes=eta_notes,
        items_total=items_total, net_kg=net_kg, item_cartons=item_cartons)


def _status(F: list[Finding]) -> tuple[str, dict[str, str], list[str]]:
    """Any Red or Data -> Blocked; only Amber -> Ready with warnings; else Ready. Sorts F in place."""
    F.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.rule_id))
    sevs = {f.severity for f in F}
    status = "Blocked" if ({"Red", "Data"} & sevs) else ("Ready with warnings" if "Amber" in sevs else "Ready")
    rule_status = {}
    for r in RULE_IDS:
        rs = {f.severity for f in F if f.rule_id == r}
        rule_status[r] = ("Red" if "Red" in rs else "Data" if "Data" in rs else "Amber" if "Amber" in rs else "Pass")
    return status, rule_status, [r for r, s in rule_status.items() if s == "Pass"]


def apply_ai_review(result: BookingResult, reviews: dict[str, dict]) -> BookingResult:
    """Attach AI reviews to ambiguous R-06 advisories. Returns a new result.

    reviews maps item description -> {"contains_dg": "yes|no|unsure", "category", "why"}.
    "yes" adds an R-06 Red labelled as an AI flag for the seller to confirm; "unsure"
    keeps the advisory with the explanation; "no" notes "likely safe". The keyword
    findings themselves are never removed, and status is recomputed here by the
    same rule as check_booking.
    """
    import copy as _copy
    res = _copy.deepcopy(result)
    new = []
    for f in res.findings:
        if not (f.rule_id == "R-06" and f.meta.get("ambiguous")):
            continue
        rv = reviews.get(str(f.meta.get("description") or "").strip())
        if not rv:
            continue
        f.meta["ai"] = rv
        if rv["contains_dg"] == "yes":
            cat = rv.get("category") if rv.get("category") not in (None, "none") else f.meta.get("category")
            new.append(Finding(
                "R-06", "Red",
                f"Flagged by AI review – please confirm: '{f.meta.get('description')}' probably contains a {cat}. {rv.get('why', '')}".strip(),
                "If it does, remove it from this shipment or use a dangerous-goods (ADR) service. "
                "If it doesn't, note why on the commercial invoice and tell the carrier.",
                sku=f.sku, meta={"source": "ai", "category": cat}))
    res.findings.extend(new)
    res.status, res.rule_status, res.rules_passed = _status(res.findings)
    return res


def check_all(bookings: list[dict], items: list[dict], today: date | None = None,
              notices: list[dict] | None = None) -> list[BookingResult]:
    """Check every booking against its items (matched by Booking ID, case-insensitive)."""
    today = today or today_london()
    by_id: dict[str, list[dict]] = {}
    for it in items or []:
        if not is_blank(it.get("booking_id")):
            by_id.setdefault(str(it["booking_id"]).strip().upper(), []).append(it)
    results = []
    for b in bookings or []:
        key = b.get("_match_id") or str(b.get("booking_id") or "").strip().upper()
        try:
            res = check_booking(b, by_id.get(key, []), today)
        except Exception as e:  # never let one bad row stop the batch
            res = check_booking({"booking_id": b.get("booking_id")}, [], today)
            res.findings.insert(0, Finding("DATA", "Data", f"This row couldn't be checked ({type(e).__name__}).",
                                           "Check the row for unusual values."))
            res.status = "Blocked"
        res.notices = [n for n in (notices or []) if n.get("booking_id") == res.booking_id]
        results.append(res)
    return results


def status_counts(results: list[BookingResult]) -> dict[str, int]:
    out = {"Blocked": 0, "Ready with warnings": 0, "Ready": 0}
    for r in results:
        out[r.status] = out.get(r.status, 0) + 1
    return out
