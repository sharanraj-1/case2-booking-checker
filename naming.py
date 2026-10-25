"""Customer-facing carrier names. The engine keeps the rate card's IDs (Carrier A/B/C);
sellers see the service names from the same rate card: Economy, Standard, Express."""

from __future__ import annotations

import re
from typing import Any

CARRIER_NAMES = {"Carrier A": "Economy", "Carrier B": "Standard", "Carrier C": "Express"}
_RE = re.compile(r"\bCarrier ([ABC])\b")


def name(carrier: str | None) -> str | None:
    return CARRIER_NAMES.get(carrier, carrier) if carrier else carrier


def brand(value: Any) -> Any:
    """Replace Carrier A/B/C with Economy/Standard/Express in every string of a JSON-like value."""
    if isinstance(value, str):
        return _RE.sub(lambda m: CARRIER_NAMES[m.group(0)], value)
    if isinstance(value, list):
        return [brand(v) for v in value]
    if isinstance(value, dict):
        return {k: brand(v) for k, v in value.items()}
    return value
