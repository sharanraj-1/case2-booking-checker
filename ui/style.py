"""Page styling and small HTML helpers. All user text is escaped before use in HTML."""

from html import escape

import streamlit as st

CSS = """
<style>
.block-container {padding-top: 3.5rem; max-width: 1200px;}
.chip {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.78rem; font-weight:600;
       line-height:1.5; margin-right:6px; white-space:nowrap;}
.chip-red {background:#FDECEC; color:#B42318;}
.chip-amber {background:#FEF4E6; color:#B54708;}
.chip-green {background:#E7F6EC; color:#067647;}
.chip-data {background:#EEF0FA; color:#3E4784;}
.chip-adv {background:#F2F4F7; color:#475467;}
.chip-blue {background:#EAF0FF; color:#2F4FC4;}
.muted {color:#667085; font-size:0.88rem;}
.kv {display:flex; justify-content:space-between; gap:12px; padding:3px 0; border-bottom:1px solid #F2F4F7; font-size:0.92rem;}
.kv span:first-child {color:#667085;}
.kv span:last-child {text-align:right; font-weight:500;}
.missing {color:#B54708; font-weight:600;}
.rulegrid {display:grid; grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); gap:6px; margin:6px 0 4px;}
.rulecell {border:1px solid #EAECF0; border-radius:8px; padding:4px 8px; font-size:0.8rem;}
abbr {text-decoration: underline dotted; cursor: help;}
@media (max-width: 640px) { .block-container {padding-left:1rem; padding-right:1rem;} }
</style>
"""

SEV_CHIP = {"Red": ("chip-red", "Red · must fix"), "Data": ("chip-data", "Data · missing or unreadable"),
            "Amber": ("chip-amber", "Amber · warning"), "Advisory": ("chip-adv", "Advisory / reference only")}
STATUS_CHIP = {"Blocked": ("chip-red", "🔴 Blocked"), "Ready with warnings": ("chip-amber", "🟠 Ready with warnings"),
               "Ready": ("chip-green", "🟢 Ready")}
RULE_CELL = {"Pass": "✅", "Red": "🔴", "Amber": "🟠", "Data": "⚪"}

GLOSSARY = {
    "HS code": "Harmonised System code: the 6–10 digit number customs use to classify a product (e.g. 691200 for ceramic tableware).",
    "Declared value": "The total value of the goods you tell customs, in GBP. It must match your commercial invoice.",
    "Gross weight": "Total weight including goods, cartons, packaging and pallets.",
    "Net weight": "Weight of the goods alone, without packaging.",
    "Commercial invoice": "The document customs use to check what's in the shipment, its value and origin.",
    "EORI number": "Economic Operators Registration and Identification number. Exporters need a GB EORI; the EU importer needs an EU EORI.",
    "Incoterms": "Standard terms (e.g. DAP, DDP) that say who pays for transport, duty and import VAT.",
    "Country of origin": "Where the goods were made, not where they ship from. It decides duty rates.",
    "ADR": "The European agreement for carrying dangerous goods by road. These services aren't ADR services.",
}


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def chip(text: str, cls: str) -> str:
    return f'<span class="chip {cls}">{escape(text)}</span>'


def abbr(term: str, label: str | None = None) -> str:
    return f'<abbr title="{escape(GLOSSARY.get(term, ""))}">{escape(label or term)}</abbr>'


def kv(label: str, value: str, missing: bool = False) -> str:
    v = '<span class="missing">missing</span>' if missing else f"<span>{escape(value)}</span>"
    return f'<div class="kv"><span>{escape(label)}</span>{v}</div>'


def glossary() -> None:
    with st.popover("📖 What do these terms mean?"):
        for k, v in GLOSSARY.items():
            st.markdown(f"**{k}**: {v}")
