"""Scripted chat conversations against the real API. Skipped when ANTHROPIC_API_KEY isn't set.

Run: ANTHROPIC_API_KEY=... pytest tests/test_chat_scripted.py -v
Each turn goes through the same path as the app: LLM extract -> chat_state.apply_patch -> engine.
"""

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chat_state  # noqa: E402
import engine  # noqa: E402

pytestmark = pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")

TODAY = date(2026, 10, 25)


def run_conversation(turns):
    from llm import extract
    st = chat_state.new_state()
    last_q = ""
    log = []
    for msg in turns:
        patch = extract.extract(msg, st, last_q)
        assert patch is not None, f"AI call failed on: {msg}"
        st, changes, problems = chat_state.apply_patch(st, patch)
        reply = chat_state.build_reply(st, changes, problems, patch.get("reply_hint"))
        last_q = " ".join(chat_state.questions(st))
        log.append((msg, changes, problems, reply))
    b, items = chat_state.engine_input(st)
    return st, engine.check_booking(b, items, TODAY), log


def test_vague_start_asks_for_missing_details():
    st, res, log = run_conversation(["I need to send some mugs to Germany next week"])
    b = st["booking"]
    assert b.get("dest_country") == "Germany" and not b.get("dest_city")
    assert st["items"] and "mug" in st["items"][0]["description"].lower()
    reply = log[-1][3]
    assert "Berlin" in reply  # asks which German city, offering the options
    assert "Germany, France" not in reply  # doesn't re-ask the country
    assert b.get("ready_date")  # "next week" resolved to a date


def test_missing_fields_then_complete():
    st, res, log = run_conversation([
        "Hi, Northfield Goods here. We want to ship 1,080 ceramic mugs at £5 each from London to Berlin.",
        "It's going to a warehouse and the delivery appointment is booked. Ready on 05-11-2026. Cheapest please.",
        "3 pallets, 620 kg in total.",
        "12 mugs per carton, each mug weighs 0.5 kg, HS code 691200, made in the UK.",
    ])
    assert chat_state.is_complete(st), chat_state.questions(st)
    assert res.status == "Ready" and res.recommendation == "Carrier A" and res.total_cost == 540
    assert st["booking"]["cartons"] == 90 and st["booking"]["declared_value"] == 5400
    for _, _, _, reply in log[:-1]:
        assert "?" in reply  # each turn asked for something still missing


def test_mid_conversation_changes():
    st, res, log = run_conversation([
        "Northfield Goods, London. 1,080 ceramic mugs at £5, 12 per carton, 0.5 kg each, HS 691200, made in the UK. "
        "Plus 200 scented candles at £9, 20 per carton, 0.3 kg each, HS 340600, made in the UK. "
        "3 pallets, 700 kg, to a warehouse in Berlin with an appointment booked, ready 05-11-2026, cheapest.",
        "Actually make it 4 pallets.",
        "Change the destination to Lyon.",
        "Drop the candles.",
        "Go with fastest.",
    ])
    b = st["booking"]
    assert b["pallets"] == 4 and b["dest_city"] == "Lyon" and b["dest_country"] == "France"
    assert len(st["items"]) == 1 and "mug" in st["items"][0]["description"].lower()
    assert b["priority"] == "Fastest" and res.recommendation == "Carrier C"
    assert any("Pallets 3 → 4" in c for c in log[1][1])
