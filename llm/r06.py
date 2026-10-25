"""AI second opinion for R-06 items the keyword screen found ambiguous."""

from __future__ import annotations

import streamlit as st

import engine
from llm import client, prompts

_ANSWERS = {"yes", "no", "unsure"}
_CATEGORIES = {"lithium battery", "aerosol", "flammable liquid", "none"}


class _ReviewFailed(Exception):
    pass


@st.cache_data(show_spinner=False, max_entries=1000)
def _classify_cached(description: str, matched: str) -> dict:
    obj = client.call_json(prompts.R06_SYSTEM, prompts.r06_user(description, matched))
    if not obj or str(obj.get("contains_dg", "")).lower() not in _ANSWERS:
        raise _ReviewFailed  # exceptions aren't cached, so a later run can try again
    cat = str(obj.get("category", "none")).lower()
    return {"contains_dg": str(obj["contains_dg"]).lower(),
            "category": cat if cat in _CATEGORIES else "none",
            "why": str(obj.get("why", ""))[:300]}


def classify(description: str, matched: str) -> dict | None:
    try:
        return _classify_cached(description.strip(), matched)
    except Exception:
        return None


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
