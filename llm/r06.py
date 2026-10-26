"""AI second opinion for R-06 items the keyword screen found ambiguous."""

from __future__ import annotations

import engine
from llm import client, prompts

_ANSWERS = {"yes", "no", "unsure"}
_CATEGORIES = {"lithium battery", "aerosol", "flammable liquid", "none"}
_cache: dict[tuple[str, str], dict] = {}  # per process; only successful reviews are kept


def classify(description: str, matched: str) -> dict | None:
    key = (description.strip(), matched)
    if key in _cache:
        return _cache[key]
    obj = client.call_json(prompts.R06_SYSTEM, prompts.r06_user(*key))
    if not obj or str(obj.get("contains_dg", "")).lower() not in _ANSWERS:
        return None  # not cached, so a later run can try again
    cat = str(obj.get("category", "none")).lower()
    review = {"contains_dg": str(obj["contains_dg"]).lower(),
              "category": cat if cat in _CATEGORIES else "none",
              "why": str(obj.get("why", ""))[:300]}
    if len(_cache) < 1000:
        _cache[key] = review
    return review


def ambiguous_items(result: engine.BookingResult) -> list[tuple[str, str]]:
    return [(f.meta["description"], f.meta.get("phrase", "")) for f in result.findings
            if f.rule_id == "R-06" and f.meta.get("ambiguous") and f.meta.get("description")]


def review(result: engine.BookingResult) -> engine.BookingResult:
    """Return the result with AI reviews attached (unchanged if no key or nothing ambiguous)."""
    todo = ambiguous_items(result)
    if not todo or not client.available():
        return result
    reviews = {}
    for desc, phrase in todo:
        r = classify(desc, phrase)
        if r:
            reviews[desc.strip()] = r
    return engine.apply_ai_review(result, reviews) if reviews else result
