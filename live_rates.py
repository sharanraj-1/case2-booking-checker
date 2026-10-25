"""Live pallet prices from Pallet2Ship's public, login-free quote form.

Advisory only: never changes a rule result, the status or our carrier pick (which uses the
fixed rate card from the brief). Used only when the seller asks ("Check live prices"),
cached for 30 minutes per route/load, with a short timeout and an honest User-Agent.
Pallet2Ship's robots.txt allows /quotes-list/; its terms don't allow deep links, so the UI
names the source without linking to it.
"""

from __future__ import annotations

import html
import json
import re
import time

import requests

BASE = "https://www.pallet2ship.co.uk"
USER_AGENT = "PalletPreFlight/1.0 (hackathon prototype; on-demand quote comparison)"
TIMEOUT = 12
CACHE_SECONDS = 30 * 60
SOURCE = "Pallet2Ship"

COUNTRY_IDS = {"United Kingdom": "1", "Germany": "8", "France": "23", "Netherlands": "40"}
POSTCODES = {"London": "EC1", "Manchester": "M1", "Birmingham": "B1", "Leeds": "LS1", "Berlin": "10115",
             "Frankfurt": "60311", "Hamburg": "20095", "Paris": "75001", "Lyon": "69001", "Amsterdam": "1012",
             "Rotterdam": "3011"}
# (form field, max kg, height cm) — Pallet2Ship's pallet types, footprint 120 x 120 cm.
PALLET_TYPES = [("packages21", 150, 60, "Mini quarter"), ("packages1", 300, 80, "Quarter"),
                ("packages2", 600, 110, "Half"), ("packages4", 750, 220, "Full lite"), ("packages3", 1200, 220, "Full")]

_cache: dict[tuple, tuple[float, dict]] = {}


def pallet_type(kg_per_pallet: float):
    return next((t for t in PALLET_TYPES if kg_per_pallet <= t[1]), None)


def parse_quotes(page: str) -> list[dict]:
    """Services and prices from the quotes page (its analytics item list), with transit times."""
    items = []
    for m in re.finditer(r'item_name:\s*"([^"]+)".{0,200}?price:\s*([\d.]+)', page, re.S):
        items.append({"service": html.unescape(m.group(1)), "price": float(m.group(2))})
    seen, out = set(), []
    for it in items:
        if it["service"] in seen:
            continue
        seen.add(it["service"])
        i = page.find(f'data-servicename="{it["service"]}"')
        transit = None
        if i != -1:
            seg = re.sub(r"<[^>]+>", " ", page[i:i + 6000])
            t = re.search(r"Transit:\s*([\d\- ]+Working days)", seg, re.I)
            transit = re.sub(r"\s+", " ", t.group(1)).strip() if t else None
        mode = "Air" if "air" in it["service"].lower() else "Road"
        out.append({**it, "transit": transit, "mode": mode})
    return sorted(out, key=lambda q: q["price"])


def quote(origin_city: str, dest_country: str, dest_city: str, pallets: int, gross_kg: float) -> dict:
    """Return {"ok", "quotes", "pallet_type", "fetched_at", "error"}. Never raises."""
    now = time.time()
    if dest_country not in COUNTRY_IDS or not pallets or not gross_kg or pallets < 1:
        return {"ok": False, "error": "Need the route, pallets and total weight first.", "quotes": []}
    pt = pallet_type(gross_kg / pallets)
    if pt is None:
        return {"ok": False, "error": "Over 1,200 kg per pallet: live quotes need more pallets.", "quotes": []}
    if pallets > 50:
        return {"ok": False, "error": "Live quotes cover up to 50 pallets.", "quotes": []}
    key = (origin_city, dest_country, dest_city, int(pallets), round(gross_kg))
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]
    field, _max, height, label = pt
    per = round(gross_kg / pallets, 1)
    data = {"ccountry_id": "1", "colpostcode": POSTCODES.get(origin_city, ""), "dcountry_id": COUNTRY_IDS[dest_country],
            "delpostcode": POSTCODES.get(dest_city, ""), "packages": str(int(pallets)), "pallet": "1",
            "bstep": "2", "showPostcode3": "1", "showPostcode4": "1", "tawb": "1", "fcl": "0", "ftl": "0",
            **{t[0]: "0" for t in PALLET_TYPES}, "packages255": "0", field: str(int(pallets))}
    for i in range(1, int(pallets) + 1):
        data.update({f"weight[{i}]": str(per), f"length[{i}]": "120", f"width[{i}]": "120", f"height[{i}]": str(height)})
    try:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        r = s.post(f"{BASE}/quotes-list/", data=data, timeout=TIMEOUT)
        quotes = parse_quotes(r.text) if r.ok else []
    except requests.RequestException:
        return {"ok": False, "error": f"{SOURCE} didn't answer in time. Try again in a minute.", "quotes": []}
    if not quotes:
        result = {"ok": False, "error": f"{SOURCE} returned no prices for this route and load.", "quotes": []}
    else:
        result = {"ok": True, "quotes": quotes, "pallet_type": f"{int(pallets)} × {label} pallet ({per:g} kg each)",
                  "fetched_at": time.strftime("%H:%M", time.localtime(now)), "error": None, "source": SOURCE}
    _cache[key] = (now, result)
    return result


if __name__ == "__main__":  # manual check: python live_rates.py
    print(json.dumps(quote("Leeds", "Germany", "Berlin", 3, 620), indent=2))
