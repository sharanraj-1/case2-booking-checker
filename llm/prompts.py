"""Prompts for the two LLM jobs: extracting booking details from chat, and R-06 review.

The model only extracts, explains and classifies. It never decides a rule result,
a booking status or the carrier; the engine does.
"""

import engine

_CITIES = "; ".join(f"{k}: {', '.join(v)}" for k, v in engine.DEST_CITIES.items())

EXTRACT_SYSTEM = f"""You turn a seller's chat message into a JSON patch for a UK -> EU pallet shipment booking.

Return ONLY one JSON object, no prose, in exactly this shape:
{{"booking_updates": {{...}}, "item_updates": [{{"op": "add|update|remove", "match_sku_or_index": ..., "fields": {{...}}}}], "reply_hint": "..."}}

booking_updates keys (include only what the seller stated or clearly changed in THIS message):
- seller: business name
- origin_city: one of {', '.join(engine.ORIGIN_CITIES)}
- dest_country: Germany, France or Netherlands
- dest_city: {_CITIES}
- dest_type: "Warehouse" or "Business address" (a shop, office, store or home business = "Business address")
- ready_date: DD-MM-YYYY. Resolve relative dates ("next Thursday", "tomorrow") using TODAY given below.
- priority: "Cheapest", "Fastest", "Most reliable" or "Balanced"
- pallets: whole number. For relative changes write a string: "add a pallet" -> "+1", "two fewer pallets" -> "-2".
- cartons: total cartons for the booking (only if stated for the whole shipment)
- declared_value: total value in GBP (only if stated)
- gross_kg: total gross weight in kg ("half a tonne" -> 500, "1.2 tonnes" -> 1200)
- appointment: "Yes" or "No" (has a delivery appointment been booked at the warehouse)

item_updates (one entry per product):
- op "add": a new product. fields may include sku, description, hs_code, qty, unit_price, units_per_carton, cartons, unit_kg, coo.
- op "update": change a product already in CURRENT ITEMS. match_sku_or_index = its SKU, its # number, or a word from its description.
- op "remove": drop a product ("drop the candles"). match_sku_or_index as above; fields = {{}}.
- coo = country where the goods were made. hs_code = digits only, as text, keep leading zeros.
- qty = units, unit_price = GBP per unit, unit_kg = kg per single unit (e.g. "mugs weigh 500g each" -> 0.5).
- For relative quantity changes use a string like "+100".

Rules:
- Never invent or guess values. If the seller didn't say it, leave it out.
- Never calculate totals, carton counts or anything else; copy the numbers as stated (relative changes as "+n"/"-n").
- If a value is ambiguous (e.g. "Germany" with no city, "Munich"), still pass what was said; the app will ask.
- Pass a city that's not on the list exactly as written (e.g. "Munich"); the app explains the options.
- If the seller answers a question from LAST QUESTION with a bare value ("4", "yes", "Lyon"), map it to that field.
- Mid-conversation changes ("actually 4 pallets", "make it Lyon", "go with fastest") are updates.
- Origin country is always the United Kingdom and currency is GBP; don't ask about them.
- reply_hint: one short, friendly sentence acknowledging what you understood. No questions; the app asks them.
- Do not judge rules, compliance, weights or carriers. That is done elsewhere.
"""


def extract_user(message: str, booking: dict, items: list[dict], last_question: str, today: str) -> str:
    import json
    shown_items = [{"#": i + 1, **{k: v for k, v in it.items() if not k.startswith("_")}} for i, it in enumerate(items)]
    shown_booking = {k: v for k, v in booking.items() if not k.startswith("_") and k != "booking_id"}
    return (f"TODAY: {today} (DD-MM-YYYY)\n"
            f"CURRENT BOOKING: {json.dumps(shown_booking, default=str)}\n"
            f"CURRENT ITEMS: {json.dumps(shown_items, default=str)}\n"
            f"LAST QUESTION: {last_question or '(none)'}\n"
            f"SELLER MESSAGE: {message}")


R06_SYSTEM = """You review one product description for a UK -> EU road pallet service that cannot carry:
lithium batteries (including devices containing them), aerosols, or flammable liquids.

Return ONLY a JSON object:
{"contains_dg": "yes|no|unsure", "category": "lithium battery|aerosol|flammable liquid|none", "why": "one plain-English sentence"}

- "yes": the product very likely is or contains one of these (e.g. a Bluetooth speaker has a lithium battery).
- "no": very likely none of these (e.g. a wired mouse, a battery-free clock, a candle).
- "unsure": it depends on the exact product; say what the seller should check.
Judge only from the description. Be concise."""


def r06_user(description: str, matched_word: str) -> str:
    return f'Product description: "{description}"\nThe word that triggered review: "{matched_word}"'
