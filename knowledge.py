"""Checked answers, export-invoice rules and country rules. Plain data, no AI.

The chatbot may only answer a seller's question by picking one of TOPICS; the text the
seller sees is always this curated text, never free model output. Everything here is
advisory: it never changes a rule result, the booking status or the carrier pick.

Sources:
- Export invoice: business.gov.uk "How to create an export invoice"
  https://www.business.gov.uk/export-from-uk/learn/categories/funding-financing-and-getting-paid/get-paid/how-create-export-invoice/
- Exporting from GB: https://www.gov.uk/export-goods
- UK-EU origin: https://www.gov.uk/guidance/claiming-preferential-rates-of-duty-between-the-uk-and-eu
"""

from __future__ import annotations

import engine
from engine import format_date, kg, money, num

INVOICE_GUIDE = ("https://www.business.gov.uk/export-from-uk/learn/categories/funding-financing-and-getting-paid/"
                 "get-paid/how-create-export-invoice/")
EXPORT_GUIDE = "https://www.gov.uk/export-goods"
ORIGIN_GUIDE = "https://www.gov.uk/guidance/claiming-preferential-rates-of-duty-between-the-uk-and-eu"
TARIFF_LOOKUP = "https://www.trade-tariff.service.gov.uk/find_commodity"

# --- Answers the chatbot is allowed to give (picked by topic id) -------------

TOPICS: dict[str, dict] = {
    "hs_code": {"q": "What is an HS code?", "a":
        "An HS code (commodity code) is the 6 to 10 digit number customs use to classify a product, for example "
        "691200 for ceramic tableware. It decides duty and any restrictions, and getting it wrong can make you liable. "
        "Look yours up on the GOV.UK Trade Tariff (trade-tariff.service.gov.uk)."},
    "declared_value": {"q": "What is the declared value?", "a":
        "It's the total value of the goods you tell customs, in GBP: quantity × unit price for every product. "
        "It must match your commercial invoice. We check it's within 1% of your product lines."},
    "gross_weight": {"q": "What's gross weight?", "a":
        "Gross weight is everything on the truck for this booking: the goods, boxes, packaging and the pallets. "
        "Net weight is the goods alone. Gross can never be less than net."},
    "commercial_invoice": {"q": "What goes on the commercial invoice?", "a":
        "A commercial (export) invoice travels with the goods and holds more than a normal UK invoice: invoice "
        "number and date; seller and buyer names, addresses and contacts; the consignee if different; related "
        "proforma/PO numbers; unit price, payment method, currency and discounts; quantity, gross and net weight and "
        "package details; HS code and a plain-English description; the Incoterms; marks and numbers on packages; "
        "country of origin; transport details; total value; extra charges like freight and insurance; and language "
        "versions or certification if the buyer's country needs them. After your check you'll get a checklist and a "
        "draft you can download."},
    "incoterms": {"q": "What are Incoterms?", "a":
        "Incoterms are standard terms you agree with your buyer that say who pays for transport, insurance, import "
        "duty and import VAT, and where responsibility passes. Common ones for EU road freight are DAP (you deliver, "
        "the buyer pays import duty and VAT) and DDP (you pay everything, including import VAT). Put the agreed term "
        "on the invoice."},
    "eori": {"q": "Do I need an EORI number?", "a":
        "Yes. To export from England, Wales or Scotland you need an EORI number starting with GB. Your buyer (the "
        "importer) needs an EU EORI to clear the goods in Germany, France or the Netherlands. Apply for a GB EORI on GOV.UK."},
    "export_declaration": {"q": "Who makes the export declaration?", "a":
        "The goods need a UK export declaration to clear UK customs. Most sellers ask their freight forwarder or a "
        "customs agent to make it for them; you can also make it yourself. The completed invoice and any licences or "
        "certificates must travel with the goods."},
    "country_of_origin": {"q": "What is country of origin?", "a":
        "It's where the goods were made, grown or produced, not where they ship from. Goods made in the UK can get "
        "the UK-EU zero tariff if they meet the rules of origin and you add a 'statement on origin' to the invoice. "
        "Goods made elsewhere (for example China) usually don't qualify unless they were sufficiently processed in the UK."},
    "statement_on_origin": {"q": "What is a statement on origin?", "a":
        "It's a set text you add to the invoice so your EU buyer can claim the zero tariff on UK-origin goods: "
        "'The exporter of the products covered by this document (Exporter Reference No [your GB EORI]) declares that, "
        "except where otherwise clearly indicated, these products are of UK preferential origin.' followed by place, "
        "date and your name. Clearly mark any lines that aren't UK origin."},
    "import_vat_duty": {"q": "Will my buyer pay import VAT or duty?", "a":
        "Usually, yes. The goods are cleared into the EU in the destination country and import VAT is charged at that "
        "country's rate (standard rates: Germany 19%, France 20%, Netherlands 21%; some goods have reduced rates). "
        "Customs duty depends on the HS code and origin; UK-origin goods with a statement on origin can be 0%. Who pays "
        "depends on the Incoterms you agree."},
    "dangerous_goods": {"q": "What can't I send?", "a":
        "These road services can't carry lithium batteries (including power banks and many rechargeable or Bluetooth "
        "devices), aerosols (sprays, hairspray, spray paint) or flammable liquids (perfume, nail polish, solvents, hand "
        "sanitiser). They need a specialist dangerous-goods (ADR) service. Some goods, like chemicals, animals or "
        "firearms, also need export licences."},
    "pallets": {"q": "How many pallets do I need?", "a":
        "Each carrier has a maximum weight per pallet: Carrier A 500 kg, Carrier B 750 kg and Carrier C 400 kg. Divide "
        "your total gross weight by the number of pallets; if it's over a carrier's limit, that carrier can't take it. "
        "Tell me the total weight and I'll work out what fits."},
    "carriers": {"q": "Which carriers do you use?", "a":
        "We compare three road services on a fixed rate card: Carrier A (economy, 5 working days, 92% on time, up to "
        "500 kg per pallet), Carrier B (standard, 3 days, 95%, up to 750 kg) and Carrier C (express, 2 days, 98%, up to "
        "400 kg). Prices per pallet depend on the destination country. Your priority decides which we pick."},
    "destinations": {"q": "Where do you deliver?", "a":
        "We collect from London, Manchester, Birmingham or Leeds and deliver to Germany (Berlin, Frankfurt, Hamburg), "
        "France (Paris, Lyon) or the Netherlands (Amsterdam, Rotterdam)."},
    "appointment": {"q": "Why do I need a delivery slot?", "a":
        "Most EU warehouses only accept trucks with a booked delivery appointment. Without one the driver can be "
        "turned away, which adds a failed-delivery fee and delay. Business addresses usually don't need one."},
    "timing": {"q": "How long does it take?", "a":
        "Transit is counted in working days from collection: 5 days (Carrier A), 3 days (Carrier B) or 2 days "
        "(Carrier C), skipping weekends and UK and destination public holidays. We'll show your estimated delivery date."},
}

TOPIC_IDS = list(TOPICS)

# Keyword fallback for guided mode (no AI): only clear matches, otherwise no answer.
_KEYWORDS = {
    "hs_code": ("hs code", "commodity code", "tariff code"), "declared_value": ("declared value",),
    "gross_weight": ("gross weight", "net weight"), "commercial_invoice": ("commercial invoice", "export invoice", "invoice"),
    "incoterms": ("incoterm", "dap", "ddp"), "eori": ("eori",), "export_declaration": ("export declaration", "customs declaration"),
    "statement_on_origin": ("statement on origin", "origin declaration"), "country_of_origin": ("country of origin",),
    "import_vat_duty": ("vat", "import duty", "duty", "tariff"), "dangerous_goods": ("dangerous", "battery", "aerosol", "can't i send", "cannot send", "prohibited"),
    "pallets": ("how many pallets", "pallet size", "per pallet"), "carriers": ("carrier", "which courier"),
    "destinations": ("where do you deliver", "which countries", "which cities"), "appointment": ("delivery slot", "appointment"),
    "timing": ("how long", "transit time", "when will it arrive"),
}


def match_topic(text: str) -> str | None:
    """Pick a topic for a typed question without AI. Only when the question is clear."""
    low = str(text).lower()
    if "?" not in low and not low.startswith(("what", "how", "why", "do i", "can i", "who", "where", "which", "when")):
        return None
    for topic, words in _KEYWORDS.items():
        if any(w in low for w in words):
            return topic
    return None

OFF_TOPIC_REPLY = ("I can only help with booking a pallet shipment from the UK to Germany, France or the Netherlands, "
                   "and the paperwork for it.")


# --- Export invoice checklist (business.gov.uk's 15 points) ------------------


def invoice_checklist(res: engine.BookingResult) -> dict:
    """What we already have for the commercial invoice, and what the seller must add."""
    b, items = res.booking, res.items
    bad = {f.rule_id for f in res.findings if f.severity in ("Red", "Data")}
    opt = res.chosen_option
    has_items = bool(items)

    def row(n, title, state, detail):
        return {"n": n, "title": title, "state": state, "detail": detail}

    rows = [
        row(1, "Invoice number and date", "add", "Give the invoice its own number and the date you issue it."),
        row(2, "Seller and buyer details", "add",
            f"Seller: {b.get('seller') or 'your business'} — add full address and contact details. "
            "Buyer: add their name, address and contact details."),
        row(3, "Consignee (final recipient)", "add",
            f"Only if different from the buyer: who receives the goods in {b.get('dest_city') or 'the EU'}."),
        row(4, "Related paperwork", "add", "The number and date of the proforma invoice, purchase order or sales contract."),
        row(5, "Unit price, payment method, currency, discounts",
            "check" if "R-02" in bad else ("ready" if has_items else "add"),
            "Unit prices and currency (GBP) come from your products. Add the payment method and any discounts."),
        row(6, "Weights and packages",
            "check" if bad & {"R-03", "R-04", "R-07"} else ("ready" if has_items else "add"),
            f"Gross {kg(b.get('gross_kg'))}, net {kg(res.net_kg)}, "
            f"{num(res.item_cartons) if res.item_cartons is not None else '?'} boxes on "
            f"{num(b.get('pallets')) if b.get('pallets') else '?'} pallets."),
        row(7, "HS code and plain-English description",
            "check" if "R-01" in bad else ("ready" if has_items else "add"),
            "From your product lines. HS codes must be right: they set duty and restrictions."),
        row(8, "Incoterms", "add", "Agree them with your buyer (for example DAP or DDP) and write them on the invoice."),
        row(9, "Marks and numbers on packages", "ready" if res.item_cartons else "add",
            f"Label boxes 1 to {num(res.item_cartons) if res.item_cartons else 'N'} with the invoice number."),
        row(10, "Country of origin", "check" if "R-09" in {f.rule_id for f in res.findings} else ("ready" if has_items else "add"),
            "Per product. Add the statement on origin for UK-made goods to claim the zero tariff."),
        row(11, "Transport details", "ready" if opt else "add",
            f"Road freight, {b.get('origin_city') or '?'} → {b.get('dest_city') or '?'}"
            + (f", {opt.carrier} ({opt.service})." if opt else ".")),
        row(12, "Total value", "check" if "R-02" in bad else ("ready" if b.get("declared_value") else "add"),
            f"{money(b.get('declared_value'))} in GBP." if b.get("declared_value") else "From your product lines."),
        row(13, "Additional charges", "ready" if res.total_cost is not None else "add",
            f"Freight {money(res.total_cost)} with {opt.carrier}; add insurance or other fees if you charge them."
            if opt and res.total_cost is not None else "Freight, insurance and any certification fees."),
        row(14, "Language versions", "info", "English is normally fine. Ask your buyer if they need a second language."),
        row(15, "Certification", "info", "Not usually needed for Germany, France or the Netherlands. Your buyer or a "
            "Chamber of Commerce can confirm."),
    ]
    counts = {s: sum(1 for r in rows if r["state"] == s) for s in ("ready", "check", "add", "info")}
    return {"rows": rows, "counts": counts, "source": INVOICE_GUIDE}


# --- Country rules ------------------------------------------------------------

COUNTRY_RULES = {
    "Germany": {"vat": "19%", "authority": "German customs (Zoll)"},
    "France": {"vat": "20%", "authority": "French customs (DGDDI)"},
    "Netherlands": {"vat": "21%", "authority": "Dutch customs (Douane)"},
}


def country_rules(res: engine.BookingResult) -> dict | None:
    b, items = res.booking, res.items
    country = b.get("dest_country")
    if country not in COUNTRY_RULES:
        return None
    c = COUNTRY_RULES[country]
    origins = sorted({str(i.get("coo")) for i in items if i.get("coo")})
    non_uk = [o for o in origins if o != "United Kingdom"]
    uk = "United Kingdom" in origins
    export = [
        "You need a GB EORI number (starts with GB) to export.",
        "Make a UK export declaration, or have your freight forwarder or customs agent make it.",
        "Check whether any product needs an export licence or certificate (for example chemicals, animals or firearms).",
        "The commercial invoice and any licences must travel with the goods. Keep copies of your invoices and customs paperwork.",
    ]
    imports = [
        f"Your buyer needs an EU EORI number; the goods are cleared by {c['authority']}.",
        f"Import VAT is charged at {country}'s rate (standard {c['vat']}; some goods have a reduced rate). "
        "Who pays it, and any duty, depends on the Incoterms you agree.",
    ]
    if uk:
        imports.append("UK-made goods can enter at 0% duty under the UK-EU agreement if they meet the rules of origin and "
                       "the invoice carries a statement on origin.")
    if non_uk:
        imports.append(f"Goods made in {', '.join(non_uk)} usually don't get the UK-EU zero tariff; the EU duty for "
                       "their HS code applies.")
    if any(f.rule_id == "R-06" for f in res.findings):
        imports.append("Dangerous goods (batteries, aerosols, flammable liquids) need a specialist ADR service and extra paperwork.")
    origin_text = None
    if uk:
        origin_text = ("The exporter of the products covered by this document (Exporter Reference No [your GB EORI]) "
                       "declares that, except where otherwise clearly indicated, these products are of UK preferential "
                       f"origin. [Place], {format_date(engine.today_london())}, {b.get('seller') or '[your name]'}")
    return {"country": country, "export": export, "import": imports, "statement_on_origin": origin_text,
            "sources": [EXPORT_GUIDE, ORIGIN_GUIDE]}
