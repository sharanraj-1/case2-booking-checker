"""Suggestions for the seller: an estimated total weight and the best number of pallets.

Planning aids only, never rule results. Every price, eligibility and pick comes from
engine.recommend() for each candidate pallet count, so suggestions always agree with the
checks the booking will get. Assumptions are stated in the text the seller sees.
"""

from __future__ import annotations

import math
from datetime import date

import engine

BOX_KG = 0.4            # a typical corrugated shipping box
PALLET_KG = 25          # a standard wooden pallet
BOXES_PER_PALLET = 60   # typical shipping boxes on a 120 x 100 cm pallet, stacked about 1.8 m high
MAX_PALLETS = 33        # a full articulated trailer


def load(items: list[dict]) -> dict | None:
    """Goods weight and box count from the products, or None if any weight is missing."""
    if not items or any(i.get("qty") is None or i.get("unit_kg") is None for i in items):
        return None
    net = sum(i["qty"] * i["unit_kg"] for i in items)
    boxes = sum(int(i["cartons"]) for i in items if i.get("cartons")) if all(i.get("cartons") for i in items) else None
    return {"net": net, "boxes": boxes}


def _options(gross: float, dest_country: str, priority: str | None, ready: date | None, today: date,
             min_pallets: int) -> list[dict]:
    lo = max(1, min_pallets, math.ceil(gross / max(c["max_kg"] for c in engine.CARRIERS)))
    hi = min(MAX_PALLETS, max(lo, math.ceil(gross / min(c["max_kg"] for c in engine.CARRIERS))) + 1)  # +1: a roomier option
    out = []
    for n in range(lo, hi + 1):
        rec = engine.recommend(gross, n, dest_country, priority, ready, today)
        opt = next((o for o in rec["options"] if o.carrier == rec["recommendation"]), None)
        if opt is None or not opt.eligible:
            continue
        out.append({"pallets": n, "per_pallet": gross / n, "carrier": opt.carrier, "cost": opt.cost,
                    "transit": opt.transit_days, "on_time": opt.on_time, "eta": opt.eta,
                    "eligible": [o.carrier for o in rec["options"] if o.eligible]})
    return out


def _rank(opts: list[dict], priority: str | None) -> list[dict]:
    if priority == "Fastest":
        key = lambda o: (o["transit"], -o["on_time"], o["cost"], o["pallets"])
    elif priority == "Most reliable":
        key = lambda o: (-o["on_time"], o["cost"], o["transit"], o["pallets"])
    elif priority == "Balanced":  # the engine already picked the balanced carrier for each count
        key = lambda o: (o["carrier"] != "Carrier B", o["cost"], o["pallets"])
    else:  # Cheapest, or no priority yet
        key = lambda o: (o["cost"], -o["on_time"], o["pallets"])
    return sorted(opts, key=key)


def suggest_pallets(booking: dict, items: list[dict], today: date, gross: float | None = None) -> dict | None:
    """Best pallet count for the seller's priority, plus a couple of alternatives."""
    dest = booking.get("dest_country")
    if dest not in engine.DEST_CITIES:
        return None
    ld = load(items)
    gross = gross if gross is not None else booking.get("gross_kg")
    if gross is None:
        est = estimate_gross(booking, items, today)
        gross = est["gross"] if est else None
    if not gross:
        return None
    min_by_space = math.ceil(ld["boxes"] / BOXES_PER_PALLET) if ld and ld["boxes"] else 1
    ready = engine.parse_date(booking.get("ready_date"))
    ranked = _rank(_options(gross, dest, booking.get("priority"), ready, today, min_by_space), booking.get("priority"))
    if not ranked:
        return None
    best = ranked[0]
    alts, seen = [], {best["pallets"]}
    for o in sorted(ranked[1:], key=lambda o: (o["pallets"] != min(x["pallets"] for x in ranked), o["cost"])):
        if o["pallets"] not in seen and len(alts) < 2:
            alts.append(o)
            seen.add(o["pallets"])
    return {"best": best, "alternatives": alts, "gross": gross, "space_min": min_by_space,
            "boxes": ld["boxes"] if ld else None}


def estimate_gross(booking: dict, items: list[dict], today: date) -> dict | None:
    """Goods + boxes + pallets. The pallet count used is the one we'd suggest for this load."""
    ld = load(items)
    if not ld:
        return None
    boxes_kg = (ld["boxes"] or 0) * BOX_KG
    packed = ld["net"] + boxes_kg
    pallets = None
    if booking.get("dest_country") in engine.DEST_CITIES:
        # Pallets add weight, which can change how many pallets are needed: settle on a count.
        n = max(1, math.ceil(ld["boxes"] / BOXES_PER_PALLET)) if ld["boxes"] else 1
        for _ in range(5):
            s = suggest_pallets(booking, items, today, gross=packed + n * PALLET_KG)
            if not s or s["best"]["pallets"] == n:
                break
            n = s["best"]["pallets"]
        pallets = n
    pallets = pallets or max(1, math.ceil(packed / 750))
    gross = packed + pallets * PALLET_KG
    return {"net": ld["net"], "boxes": ld["boxes"], "boxes_kg": boxes_kg, "pallets": pallets,
            "pallets_kg": pallets * PALLET_KG, "gross": int(math.ceil(gross / 5.0) * 5)}
