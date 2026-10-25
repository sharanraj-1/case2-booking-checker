"""Nearest served city/country for places we don't serve. Deterministic (coordinates), no AI."""

from __future__ import annotations

import math
import re
import unicodedata

import engine

# name: (lat, lon, country). Served cities first, then common places sellers mention.
PLACES: dict[str, tuple[float, float, str]] = {
    "London": (51.507, -0.128, "United Kingdom"), "Manchester": (53.481, -2.243, "United Kingdom"),
    "Birmingham": (52.486, -1.890, "United Kingdom"), "Leeds": (53.801, -1.549, "United Kingdom"),
    "Berlin": (52.520, 13.405, "Germany"), "Frankfurt": (50.110, 8.682, "Germany"), "Hamburg": (53.551, 9.994, "Germany"),
    "Paris": (48.857, 2.352, "France"), "Lyon": (45.764, 4.836, "France"),
    "Amsterdam": (52.368, 4.904, "Netherlands"), "Rotterdam": (51.924, 4.478, "Netherlands"),
    # UK
    "Glasgow": (55.864, -4.252, "United Kingdom"), "Edinburgh": (55.953, -3.189, "United Kingdom"),
    "Liverpool": (53.408, -2.991, "United Kingdom"), "Bristol": (51.455, -2.588, "United Kingdom"),
    "Sheffield": (53.381, -1.470, "United Kingdom"), "Newcastle": (54.978, -1.618, "United Kingdom"),
    "Nottingham": (52.954, -1.158, "United Kingdom"), "Leicester": (52.637, -1.140, "United Kingdom"),
    "Cardiff": (51.481, -3.179, "United Kingdom"), "Belfast": (54.597, -5.930, "United Kingdom"),
    "Southampton": (50.910, -1.404, "United Kingdom"), "Oxford": (51.752, -1.258, "United Kingdom"),
    "Cambridge": (52.205, 0.122, "United Kingdom"), "Bradford": (53.795, -1.759, "United Kingdom"),
    "Coventry": (52.407, -1.512, "United Kingdom"), "Reading": (51.455, -0.978, "United Kingdom"),
    "Brighton": (50.822, -0.137, "United Kingdom"), "York": (53.960, -1.087, "United Kingdom"),
    "Hull": (53.768, -0.333, "United Kingdom"), "Norwich": (52.630, 1.297, "United Kingdom"),
    "Plymouth": (50.375, -4.143, "United Kingdom"), "Aberdeen": (57.150, -2.094, "United Kingdom"),
    "Stoke": (53.003, -2.180, "United Kingdom"), "Wolverhampton": (52.587, -2.129, "United Kingdom"),
    "Milton Keynes": (52.041, -0.759, "United Kingdom"), "Dover": (51.128, 1.313, "United Kingdom"),
    # Germany
    "Munich": (48.135, 11.582, "Germany"), "Cologne": (50.937, 6.960, "Germany"), "Dusseldorf": (51.227, 6.773, "Germany"),
    "Stuttgart": (48.776, 9.183, "Germany"), "Dortmund": (51.514, 7.468, "Germany"), "Essen": (51.456, 7.012, "Germany"),
    "Leipzig": (51.340, 12.375, "Germany"), "Bremen": (53.079, 8.802, "Germany"), "Dresden": (51.050, 13.737, "Germany"),
    "Hanover": (52.375, 9.732, "Germany"), "Nuremberg": (49.452, 11.077, "Germany"), "Bonn": (50.737, 7.098, "Germany"),
    "Mannheim": (49.487, 8.466, "Germany"), "Kiel": (54.323, 10.123, "Germany"),
    # France
    "Marseille": (43.296, 5.370, "France"), "Lille": (50.629, 3.057, "France"), "Toulouse": (43.605, 1.444, "France"),
    "Nice": (43.710, 7.262, "France"), "Nantes": (47.218, -1.554, "France"), "Strasbourg": (48.573, 7.752, "France"),
    "Bordeaux": (44.838, -0.579, "France"), "Montpellier": (43.611, 3.877, "France"), "Rennes": (48.117, -1.678, "France"),
    "Grenoble": (45.188, 5.724, "France"), "Reims": (49.258, 4.032, "France"), "Le Havre": (49.494, 0.107, "France"),
    "Dijon": (47.322, 5.041, "France"), "Calais": (50.951, 1.858, "France"),
    # Netherlands
    "Utrecht": (52.091, 5.122, "Netherlands"), "The Hague": (52.070, 4.300, "Netherlands"),
    "Eindhoven": (51.441, 5.470, "Netherlands"), "Groningen": (53.219, 6.567, "Netherlands"),
    "Tilburg": (51.560, 5.091, "Netherlands"), "Almere": (52.351, 5.264, "Netherlands"), "Breda": (51.589, 4.776, "Netherlands"),
    "Nijmegen": (51.842, 5.853, "Netherlands"), "Haarlem": (52.387, 4.646, "Netherlands"), "Arnhem": (51.985, 5.899, "Netherlands"),
    "Maastricht": (50.851, 5.691, "Netherlands"),
    # Nearby countries we don't serve
    "Brussels": (50.850, 4.352, "Belgium"), "Antwerp": (51.219, 4.402, "Belgium"), "Luxembourg City": (49.612, 6.130, "Luxembourg"),
    "Vienna": (48.208, 16.373, "Austria"), "Zurich": (47.377, 8.542, "Switzerland"), "Geneva": (46.204, 6.143, "Switzerland"),
    "Milan": (45.464, 9.190, "Italy"), "Madrid": (40.417, -3.704, "Spain"), "Barcelona": (41.385, 2.173, "Spain"),
    "Copenhagen": (55.676, 12.568, "Denmark"), "Warsaw": (52.230, 21.012, "Poland"), "Prague": (50.075, 14.438, "Czechia"),
    "Dublin": (53.350, -6.260, "Ireland"),
}
ALIASES = {"munchen": "Munich", "muenchen": "Munich", "koln": "Cologne", "koeln": "Cologne", "duesseldorf": "Dusseldorf",
           "nurnberg": "Nuremberg", "nuernberg": "Nuremberg", "hannover": "Hanover", "denhaag": "The Hague",
           "thehague": "The Hague", "shertogenbosch": "Eindhoven", "bruxelles": "Brussels", "brussel": "Brussels",
           "wien": "Vienna", "zurich": "Zurich", "milano": "Milan", "frankfurtammain": "Frankfurt",
           "newcastleupontyne": "Newcastle", "stokeontrent": "Stoke", "luxembourg": "Luxembourg City"}
COUNTRY_NEAR = {
    "belgium": ["Netherlands", "France"], "luxembourg": ["Germany", "France"], "austria": ["Germany"],
    "switzerland": ["Germany", "France"], "poland": ["Germany"], "denmark": ["Germany"], "czechia": ["Germany"],
    "czechrepublic": ["Germany"], "spain": ["France"], "italy": ["France"], "portugal": ["France"],
    "monaco": ["France"], "sweden": ["Germany"], "norway": ["Germany"],
}


def _key(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def find_place(name: str) -> str | None:
    k = _key(name)
    if k in ALIASES:
        return ALIASES[k]
    for p in PLACES:
        if _key(p) == k:
            return p
    return None


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    (la1, lo1), (la2, lo2) = [(math.radians(x), math.radians(y)) for x, y in (a, b)]
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def nearest_served(name: str, origin: bool = False) -> dict | None:
    """Closest city we serve to a place we don't, e.g. Munich -> Frankfurt (~300 km)."""
    place = find_place(name)
    if not place:
        return None
    lat, lon, country = PLACES[place]
    served = engine.ORIGIN_CITIES if origin else [c for cs in engine.DEST_CITIES.values() for c in cs]
    best = min(served, key=lambda c: _km((lat, lon), PLACES[c][:2]))
    return {"place": place, "place_country": country, "city": best, "country": PLACES[best][2],
            "km": int(round(_km((lat, lon), PLACES[best][:2]), -1))}


def nearest_countries(name: str) -> list[str]:
    return COUNTRY_NEAR.get(_key(name), [])
