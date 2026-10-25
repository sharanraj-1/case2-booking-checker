"""Chat extraction with guardrails: seller message -> intent, topic and a grounded patch.

Guardrails (code, not prompt):
- the model's output is reduced to known keys and allowed values;
- every number, place, HS code and name it extracts must be traceable to the seller's own
  words ("grounding"), otherwise it is dropped, so the model can't invent values;
- the reply the seller sees is built elsewhere from curated text, never from model output.
"""

from __future__ import annotations

import re

import engine
import geo
import knowledge
from llm import client, prompts

INTENTS = {"booking", "question", "greeting", "off_topic"}
MAX_CHARS = 1500

_WORDS = {"a": 1, "an": 1, "one": 1, "another": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
          "forty": 40, "fifty": 50, "hundred": 100, "dozen": 12, "half": 0.5, "quarter": 0.25}
_DATE_WORDS = re.compile(r"\d|today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|"
                         r"month|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|next|asap|soon", re.I)
_NUM_FIELDS = {"pallets", "cartons", "declared_value", "gross_kg"}
_ITEM_NUM_FIELDS = {"qty", "unit_price", "units_per_carton", "cartons", "unit_kg"}


def _numbers(msg: str) -> set[float]:
    out: set[float] = set()
    low = msg.lower()
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?|\.\d+)\s*(k\b|thousand)?", low):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        out.add(v * 1000 if m.group(2) else v)
    for w, v in _WORDS.items():
        if re.search(rf"\b{w}\b", low):
            out.add(float(v))
    scaled = set()
    for v in out:  # unit conversions the model is allowed to do: tonnes->kg, g->kg, pence->pounds
        scaled |= {v * 1000, v / 1000, v / 100}
    if "half a tonne" in low or "half a ton" in low:
        scaled.add(500.0)
    return out | scaled


def _num_ok(value, nums: set[float]) -> bool:
    s = str(value).strip()
    m = re.fullmatch(r"([+-])\s*(\d+(?:\.\d+)?)", s)
    if m:
        return float(m.group(2)) in nums or (m.group(2) == "1")  # "add a pallet", "one more"
    v = engine.parse_number(value)
    return v is not None and any(abs(v - n) < 1e-6 * max(1, abs(n)) for n in nums)


def _text_ok(value, low: str) -> bool:
    k = geo._key(str(value))
    if not k:
        return False
    msg = geo._key(low)
    if k[:4] in msg:
        return True
    aliases = [a for a, target in geo.ALIASES.items() if geo._key(target) == k]
    if any(a[:5] in msg for a in aliases):
        return True
    if k in ("unitedkingdom", "uk") and re.search(r"\b(uk|u\.k|brit|engl|scot|wales|welsh|gb)", low):
        return True
    return False


def ground(patch: dict, message: str, last_question: str) -> tuple[dict, list[str]]:
    """Drop extracted values that can't be traced to the seller's words. Returns (patch, dropped labels)."""
    low = message.lower()
    nums = _numbers(message)
    dropped: list[str] = []
    bare = len(message.split()) <= 4  # a short answer to the last question, e.g. "yes", "the warehouse"
    bu = {}
    for k, v in (patch.get("booking_updates") or {}).items():
        if k not in prompts_booking_keys():
            continue
        ok = True
        if k in _NUM_FIELDS:
            ok = _num_ok(v, nums)
        elif k in ("dest_city", "origin_city", "seller"):
            ok = _text_ok(v, low)
        elif k == "dest_country":
            ok = _text_ok(v, low) or _text_ok(patch["booking_updates"].get("dest_city", ""), low)
        elif k == "ready_date":
            ok = bool(_DATE_WORDS.search(low))
        elif k == "appointment":
            ok = bare or bool(re.search(r"appoint|slot|book|yes|no|not yet", low))
        if ok:
            bu[k] = v
        else:
            dropped.append(engine.FIELD_LABELS.get(k, k).lower())
    items = []
    for u in patch.get("item_updates") or []:
        if not isinstance(u, dict):
            continue
        fields = {}
        for k, v in (u.get("fields") or {}).items():
            ok = True
            if k in _ITEM_NUM_FIELDS:
                ok = _num_ok(v, nums)
            elif k == "hs_code":
                ok = re.sub(r"\D", "", str(v)) in re.sub(r"[^\d]", "", message) and bool(re.sub(r"\D", "", str(v)))
            elif k == "coo":
                ok = _text_ok(v, low) or bool(re.search(r"\b(made|origin|manufactur|from)\b", low)) and _text_ok(v, low)
            elif k == "description":
                words = [w for w in re.findall(r"[a-z]{3,}", str(v).lower())]
                ok = not words or any(w.rstrip("s")[:5] in low for w in words)
            if ok:
                fields[k] = v
            else:
                dropped.append(engine.FIELD_LABELS.get(k, k).lower())
        if u.get("op") == "remove" or fields:
            items.append({**u, "fields": fields})
    return {"booking_updates": bu, "item_updates": items}, dropped


def prompts_booking_keys() -> set[str]:
    return {"seller", "origin_city", "dest_country", "dest_city", "dest_type", "ready_date", "priority", "pallets",
            "cartons", "declared_value", "gross_kg", "appointment"}


def extract(message: str, state: dict, last_question: str = "") -> dict | None:
    """Return {"intent", "topic", "booking_updates", "item_updates", "dropped"}, or None if the AI is unavailable."""
    message = str(message)[:MAX_CHARS]
    user = prompts.extract_user(message, state["booking"], state["items"], last_question,
                                engine.format_date(engine.today_london()))
    obj = client.call_json(prompts.EXTRACT_SYSTEM, user)
    if obj is None:
        return None
    intent = obj.get("intent") if obj.get("intent") in INTENTS else "booking"
    topic = obj.get("topic") if obj.get("topic") in knowledge.TOPICS else None
    raw = {"booking_updates": obj.get("booking_updates") if isinstance(obj.get("booking_updates"), dict) else {},
           "item_updates": [u for u in obj.get("item_updates") or [] if isinstance(u, dict)]
           if isinstance(obj.get("item_updates"), list) else []}
    if intent == "off_topic":
        raw = {"booking_updates": {}, "item_updates": []}
    patch, dropped = ground(raw, message, last_question)
    return {**patch, "intent": intent, "topic": topic, "dropped": dropped}
