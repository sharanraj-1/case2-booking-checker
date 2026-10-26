"""How the assistant talks: warm, varied, and always built in code from what we know.

The AI never writes what the seller sees. These templates repeat back what was understood,
explain suggestions with real numbers, and keep every message on the booking.
"""

from __future__ import annotations

import engine
import naming
import planner
from engine import kg, money, num

import re

NAME = "Piper"
OPENERS = ["Lovely", "Perfect", "Great", "Brilliant", "Got it", "Nice one"]
EDIT_OPENERS = ["Done", "All sorted", "Updated", "No problem"]

WELCOME_AI = (f"Hi, I'm {NAME} 👋 I'll get your pallets booked to Europe and check the paperwork before anything leaves. "
              "Tell me what you're sending in your own words, or just tap the answers as we go.")
WELCOME_GUIDED = (f"Hi, I'm {NAME} 👋 I'll get your pallets booked to Europe and check the paperwork before anything "
                  "leaves. Just tap the answers as we go; it takes about a minute.")
DONE = ("That's everything! 🎉 Your pre-flight check is just below: the carrier I'd pick, the price, and anything "
        "to sort before collection.")
DONE_AGAIN = "Done, and I've re-checked everything below for you."
OFF_TOPIC = ("Ha, I wish I could help with that! I'm only set up for pallet shipments from the UK to Germany, France "
             "and the Netherlands, and the paperwork that goes with them.")
UNKNOWN_QUESTION = ("Good question, but I don't have a checked answer for that one, and I'd rather not guess. "
                    "I can help with your booking and its customs paperwork.")
GREETING = "Hey there! 👋"
CALCULATED = "I've worked out the box count and declared value from your products, so you don't need to."


def _pick(options: list[str], turn: int) -> str:
    return options[turn % len(options)]


def _nice_date(ddmmyyyy: str | None) -> str:
    d = engine.parse_date(ddmmyyyy)
    return d.strftime("%A %d %B").replace(" 0", " ") if d else str(ddmmyyyy)


def _phrase(field: str, value, b: dict) -> str | None:
    if value in (None, ""):
        return None
    if field == "seller":
        return f"nice to meet you, {value}"
    if field == "origin_city":
        return f"collecting from {value}"
    if field == "dest_country":
        return f"{'the Netherlands' if value == 'Netherlands' else value} it is"
    if field == "dest_city":
        return f"{value}{', ' + b['dest_country'] if b.get('dest_country') else ''}"
    if field == "dest_type":
        return "going to a warehouse" if value == "Warehouse" else "going to a business address"
    if field == "appointment":
        return "delivery slot booked" if value == "Yes" else "no delivery slot yet, noted"
    if field == "ready_date":
        return f"ready on {_nice_date(value)}"
    if field == "priority":
        return {"Cheapest": "keeping it cheap", "Fastest": "going for speed", "Most reliable": "reliability first",
                "Balanced": "a good balance of everything"}.get(value, str(value))
    if field == "pallets":
        return f"{num(value)} pallet{'' if value == 1 else 's'}"
    if field == "gross_kg":
        return f"{kg(value)} in total"
    return None


def ack(old: dict, new: dict, turn: int) -> str:
    """Repeat back what changed this turn, in plain words."""
    ob, nb = old["booking"], new["booking"]
    fresh, edits = [], []
    for f in ("dest_country", "dest_city", "priority", "ready_date", "gross_kg", "pallets", "dest_type",
              "appointment", "origin_city", "seller"):
        if f == "dest_country" and nb.get("dest_city") != ob.get("dest_city"):
            continue  # the city line already names the country
        if nb.get(f) != ob.get(f) and nb.get(f) not in (None, ""):
            p = _phrase(f, nb[f], nb)
            if ob.get(f) not in (None, ""):
                edits.append(f"{engine.FIELD_LABELS[f].lower()} changed from {_short(f, ob[f])} to {_short(f, nb[f])}")
            elif p:
                fresh.append(p)
    oi = {i.get("sku"): i for i in old["items"]}
    for it in new["items"]:
        if it.get("sku") not in oi and it.get("description"):
            q = it.get("qty")
            fresh.append(f"{num(q)} × {it['description']}" if q else str(it["description"]))
    gone = [i.get("description") or "that product" for s, i in oi.items() if s not in {x.get("sku") for x in new["items"]}]
    edits += [f"removed the {g}" for g in gone]
    parts = []
    if len(fresh) > 3:  # lots at once: summarise instead of listing everything
        parts.append(summary(nb, new["items"], turn))
    elif fresh:
        parts.append(f"{_pick(OPENERS, turn)}: {_join(fresh)}.")
    if edits:
        parts.append(f"{_pick(EDIT_OPENERS, turn)}, {_join(edits)}.")
    return " ".join(parts)


def summary(b: dict, items: list[dict], turn: int) -> str:
    """'Brilliant, that's most of it sorted: 1,080 ceramic mugs from London to Berlin, keeping it cheap.'"""
    hello = f"Nice to meet you, {b['seller']}! " if b.get("seller") else ""
    goods = (f"{num(items[0]['qty'])} {_lower_first(items[0]['description'])}" if len(items) == 1 and items[0].get("qty")
             and items[0].get("description") else f"{len(items)} products" if items else "your shipment")
    route = (f" from {b['origin_city']}" if b.get("origin_city") else "") + (f" to {b['dest_city']}" if b.get("dest_city") else
                                                                             f" to {b['dest_country']}" if b.get("dest_country") else "")
    extra = [p for p in (_phrase("priority", b.get("priority"), b), _phrase("ready_date", b.get("ready_date"), b)) if p]
    tail = f", {_join(extra)}" if extra else ""
    return f"{hello}{_pick(OPENERS, turn)}, that's most of it sorted: {goods}{route}{tail}."


AFFIRM = re.compile(r"^\s*(yes|yep|yeah|yup|sure|ok(ay)?|sounds (good|great|right)|perfect|great|fine|that works|do (that|it)|"
                    r"go (with|for) (that|it|this|your|the)|use (that|it|this|your|the)|take (that|it|your|the)|"
                    r"(your|the|that) (estimate|suggestion|recommendation))\b", re.I)


def accepts_suggestion(text: str) -> bool:
    """'yes', 'sounds good', 'go with your suggestion', 'use the estimate'..."""
    return bool(AFFIRM.search(text or ""))


def _short(field: str, v) -> str:
    if field == "gross_kg":
        return kg(v)
    if field == "pallets":
        return num(v)
    if field == "ready_date":
        return _nice_date(v)
    return str(v)


def _lower_first(s: str) -> str:
    """'Ceramic mugs' -> 'ceramic mugs' mid-sentence, but leave codes like 'LED lamps' alone."""
    return s if len(s) > 1 and s[:2].isupper() else s[:1].lower() + s[1:]


def _join(xs: list[str]) -> str:
    xs = [x[0].lower() + x[1:] if i else x for i, x in enumerate(xs)]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def question(ask: dict | None, state: dict) -> str:
    """The conversational version of the next question (the card below shows the controls)."""
    if not ask:
        return DONE
    b, items = state["booking"], state["items"]
    f = ask["field"]
    if f == "dest_country":
        return "Where's it heading? We deliver to Germany, France and the Netherlands."
    if f == "dest_city":
        return ask["question"]
    if f == "items" and ask.get("item_index") is None:
        return "What are you sending? Tell me the product, how many, and the price each, or fill in the card below."
    if f == "items":
        label = items[ask["item_index"]].get("description") or "product"
        return f"Just a few details about the {label} for the customs paperwork."
    if f == "priority":
        return "What matters most for this one: price, speed, reliability, or a good balance of all three?"
    if f == "ready_date":
        return "When will everything be ready for us to collect?"
    if f == "gross_kg":
        est = ask.get("estimate")
        if est:
            what = _lower_first(items[0].get("description") or "goods") if len(items) == 1 else "products"
            return (f"How heavy is the whole lot? I've done the maths for you: your {what} weigh {kg(est['net'])}, plus "
                    f"about {kg(est['boxes_kg'])} of boxes and {kg(est['pallets_kg'])} for {est['pallets']} "
                    f"pallet{'' if est['pallets'] == 1 else 's'}, so roughly **{kg(est['gross'])}**. Tap that below, "
                    "or type your weighed total if you have it.")
        return "How heavy is everything in total, including boxes and pallets?"
    if f == "pallets":
        s = ask.get("plan")
        if s:
            best = s["best"]
            n = best["pallets"]
            why = {"Fastest": "so the fastest service can take it",
                   "Most reliable": "so the most reliable service can take it"}.get(b.get("priority"), "which keeps the price down")
            space = (f" ({s['boxes']} boxes need at least {s['space_min']} pallet{'' if s['space_min'] == 1 else 's'} of space.)"
                     if s.get("boxes") and s["space_min"] > 1 else "")
            return (f"I'd go with **{n} pallet{'' if n == 1 else 's'}**: about {kg(round(best['per_pallet']))} each, "
                    f"{why}. That's **{naming.name(best['carrier'])} for {money(best['cost'])}**, arriving "
                    f"{best['eta'].strftime('%a %d %b').replace(' 0', ' ') if best.get('eta') else 'on time'}.{space}")
        return "How many pallets will it be?"
    if f == "dest_type":
        return "Is it going to a warehouse, or to a business like a shop or office?"
    if f == "appointment":
        return "Has the warehouse given you a delivery slot yet? Most won't accept a truck without one."
    if f == "origin_city":
        return "Nearly there! Where should we collect from?"
    if f == "seller":
        return "Last one: what's your business called?"
    return ask["question"]


def dropped(fields: list[str]) -> str:
    names = list(dict.fromkeys(fields))
    return (f"I couldn't spot the {_join(names)} in your message, so I've left "
            f"{'it' if len(names) == 1 else 'them'} for now.")
