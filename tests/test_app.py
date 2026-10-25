"""Headless UI tests with Streamlit AppTest (no browser, no API key)."""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from streamlit.testing.v1 import AppTest  # noqa: E402


@pytest.fixture(autouse=True)
def no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(ROOT)


def _app():
    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=60).run()
    assert not at.exception, at.exception
    return at


def _texts(at):
    return " ".join(m.value for m in at.markdown) + " " + " ".join(
        str(x.value) for kind in (at.error, at.warning, at.success, at.info, at.caption) for x in kind)


def test_starts_without_key_in_form_mode():
    at = _app()
    assert any("step-by-step form" in i.value for i in at.info)


def test_sample_file_every_booking_renders():
    at = _app()
    next(b for b in at.button if "sample" in b.label.lower()).click().run()
    assert not at.exception, at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Bookings"] == "18"
    assert metrics["🔴 Blocked"] == "8" and metrics["🟠 Ready with warnings"] == "4" and metrics["🟢 Ready"] == "6"
    ids = [o.split(" · ")[0] for o in next(s for s in at.selectbox if s.label == "Booking").options]
    assert len(ids) == 18
    for bid in ids:
        next(s for s in at.selectbox if s.label == "Booking").set_value(bid).run()
        assert not at.exception, (bid, at.exception)
        text = _texts(at)
        assert "Recommended:" in text, bid
        assert ("Not booked yet" in text) or ("Booking summary" in text), bid
        assert "What happens next" in text, bid


def test_apply_fix_in_file_mode():
    at = _app()
    next(b for b in at.button if "sample" in b.label.lower()).click().run()
    next(s for s in at.selectbox if s.label == "Booking").set_value("BK-003").run()
    fix = next(b for b in at.button if b.label.startswith("Apply this fix"))
    assert "£6,000.00" in fix.label
    fix.click().run()
    assert not at.exception, at.exception
    text = _texts(at)
    assert "Ready to book" in text and "Edited here" in text


def test_chat_ui_with_fake_ai(monkeypatch):
    """The AI chat path end to end, with canned extractor output instead of the API."""
    from llm import client, extract
    canned = {
        "first": {"booking_updates": {"seller": "Northfield Goods", "origin_city": "London", "dest_city": "Berlin",
                                      "dest_type": "warehouse", "appointment": "yes", "ready_date": "05-11-2026",
                                      "priority": "cheapest", "pallets": 3, "gross_kg": 620},
                  "item_updates": [{"op": "add", "fields": {"description": "Ceramic mug", "hs_code": "691200",
                                                            "qty": 1080, "unit_price": 5, "units_per_carton": 12,
                                                            "unit_kg": 0.5, "coo": "UK"}}],
                  "reply_hint": "Got it: mugs to Berlin."},
        "add a pallet": {"booking_updates": {"pallets": "+1"}, "item_updates": [], "reply_hint": "Sure."},
    }
    monkeypatch.setattr(client, "available", lambda: True)
    monkeypatch.setattr(extract, "extract", lambda msg, state, last_q="": canned["add a pallet" if "pallet" in msg else "first"])
    at = _app()
    at.chat_input[0].set_value("Northfield Goods mugs to Berlin...").run()
    assert not at.exception, at.exception
    at.chat_input[0].set_value("add a pallet").run()
    assert not at.exception, at.exception
    notes = " ".join(c.value for c in at.caption)
    assert "Pallets 3 → 4" in notes and "Cost £540.00 → £720.00" in notes
    next(b for b in at.button if "Confirm booking" in b.label).click().run()
    assert "Booking confirmed" in _texts(at)


def test_guided_form_reaches_a_result():
    at = _app()
    at.selectbox(key="gf_origin").set_value("London")
    at.radio(key="gf_country").set_value("Germany").run()
    at.selectbox(key="gf_city_Germany").set_value("Berlin")
    next(b for b in at.button if b.label.startswith("Next")).click().run()
    at.text_input(key="gf_seller").input("Northfield Goods")
    at.radio(key="gf_dtype").set_value("Warehouse").run()
    at.radio(key="gf_appt").set_value("Yes")
    from datetime import date
    at.date_input(key="gf_ready").set_value(date(2026, 11, 5))
    at.radio(key="gf_prio").set_value("Cheapest")
    next(b for b in at.button if b.label.startswith("Next")).click().run()
    at.number_input(key="gf_pallets").set_value(3)
    at.number_input(key="gf_gross").set_value(620.0)
    next(b for b in at.button if b.label.startswith("Next")).click().run()
    assert not at.exception, at.exception
    # Item entry goes through the same merge as chat; set it directly for the test.
    import chat_state
    chat = at.session_state["chat"]
    chat["state"], _, _ = chat_state.apply_patch(chat["state"], {"item_updates": [{"op": "add", "fields": {
        "description": "Ceramic mug", "hs_code": "691200", "qty": 1080, "unit_price": 5, "units_per_carton": 12,
        "unit_kg": 0.5, "coo": "United Kingdom"}}]})
    chat["form_step"] = 4
    at.run()
    assert not at.exception, at.exception
    next(b for b in at.button if "Confirm booking" in b.label).click().run()
    assert not at.exception, at.exception
    text = _texts(at)
    assert "Booking confirmed" in text and "Carrier A" in text and "£540.00" in text
