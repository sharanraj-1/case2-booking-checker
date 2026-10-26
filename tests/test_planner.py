"""Weight and pallet suggestions, and the assistant's voice."""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge  # noqa: E402
import engine  # noqa: E402
import planner  # noqa: E402
import voice  # noqa: E402

TODAY = date(2026, 10, 26)
MUGS = [{"sku": "M1", "description": "ceramic mugs", "qty": 1080, "unit_price": 5, "units_per_carton": 12,
         "cartons": 90, "unit_kg": 0.5, "hs_code": "691200", "coo": "United Kingdom"}]


def booking(prio):
    return {"dest_country": "Germany", "dest_city": "Berlin", "priority": prio, "ready_date": "05-11-2026"}


def test_weight_estimate_is_goods_plus_boxes_plus_pallets():
    e = planner.estimate_gross(booking("Cheapest"), MUGS, TODAY)
    assert e["net"] == 540 and e["boxes_kg"] == 90 * planner.BOX_KG
    assert e["pallets"] == 2 and e["pallets_kg"] == 2 * planner.PALLET_KG
    assert e["gross"] == 630  # 540 + 36 + 50 = 626, rounded up to the next 5 kg
    assert planner.estimate_gross(booking("Cheapest"), [{"qty": 5}], TODAY) is None  # no unit weight, no guess


def test_pallet_suggestion_follows_priority_and_engine_prices():
    picks = {}
    for prio in ("Cheapest", "Fastest", "Most reliable", "Balanced"):
        s = planner.suggest_pallets(booking(prio), MUGS, TODAY, gross=630)
        b = s["best"]
        rec = engine.recommend(630, b["pallets"], "Germany", prio, engine.parse_date("05-11-2026"), TODAY)
        assert rec["recommendation"] == b["carrier"]  # the engine agrees with the suggestion
        picks[prio] = (b["pallets"], b["carrier"], b["cost"])
    assert picks["Cheapest"] == (2, "Carrier A", 360)   # cheaper than the template's 3 pallets (£540)
    assert picks["Fastest"] == (2, "Carrier C", 680)    # 315 kg each keeps Express (400 kg) open
    assert picks["Balanced"][1] == "Carrier B"


def test_space_sets_a_minimum_pallet_count():
    light = [{**MUGS[0], "unit_kg": 0.05, "cartons": 300, "qty": 3600}]  # light but bulky: 300 boxes
    s = planner.suggest_pallets(booking("Cheapest"), light, TODAY, gross=400)
    assert s["best"]["pallets"] >= 300 // planner.BOXES_PER_PALLET


def test_heavy_load_matches_the_engines_none_fit_example():
    tiles = [{"qty": 1000, "unit_kg": 2.3, "cartons": 100, "unit_price": 4.5, "units_per_carton": 10}]
    s = planner.suggest_pallets(booking("Cheapest"), tiles, TODAY, gross=2400)
    assert (s["best"]["pallets"], s["best"]["carrier"], s["best"]["cost"]) == (4, "Carrier B", 880)


def _state_at(field):
    sess = bridge.new_session()
    st = sess["chat"]["state"]
    st["booking"].update({"dest_country": "Germany", "dest_city": "Berlin", "priority": "Cheapest", "ready_date": "05-11-2026"})
    st["items"] = [dict(MUGS[0])]
    if field == "pallets":
        st["booking"]["gross_kg"] = 630
    return sess


def test_weight_question_offers_the_estimate():
    sess = _state_at("gross_kg")
    ask = bridge.next_ask(sess["chat"]["state"])
    assert ask["field"] == "gross_kg" and ask["suggestions"][0]["value"] == "630" and ask["suggestions"][0]["suggested"]
    text = voice.question(ask, sess["chat"]["state"])
    assert "540 kg" in text and "630 kg" in text and "2 pallets" in text


def test_pallet_question_recommends_with_price_and_alternatives():
    sess = _state_at("pallets")
    ask = bridge.next_ask(sess["chat"]["state"])
    assert ask["field"] == "pallets"
    sug = ask["suggestions"]
    assert sug[0]["value"] == "2" and sug[0]["suggested"] and "Economy" in sug[0]["hint"] and "£360.00" in sug[0]["hint"]
    assert len(sug) >= 2 and not sug[1]["suggested"]
    text = voice.question(ask, sess["chat"]["state"])
    assert "2 pallets" in text and "Economy for £360.00" in text
    assert "plan" not in bridge._public_ask(ask)  # internal objects never reach the UI


def test_suggested_pallets_flow_through_to_a_good_booking():
    sess = _state_at("pallets")
    bridge.handle_event(sess, {"id": "p1", "type": "answer", "field": "pallets", "value": "2"}, today=TODAY)
    for f, v in (("dest_type", "Warehouse"), ("appointment", "Yes"), ("origin_city", "London"), ("seller", "Northfield")):
        bridge.handle_event(sess, {"id": f, "type": "answer", "field": f, "value": v}, today=TODAY)
    r = bridge.payload(sess, today=TODAY)["chat"]["result"]
    assert r["view"]["label"] == "Good to go" and r["recommendation"] == "Economy" and r["confirmation"]["cost"] == "£360.00"


def test_replies_repeat_back_what_was_understood_and_vary():
    old = {"booking": {}, "items": []}
    new = {"booking": {"dest_city": "Berlin", "dest_country": "Germany", "pallets": 3}, "items": []}
    a0, a1 = voice.ack(old, new, 0), voice.ack(old, new, 1)
    assert "Berlin, Germany" in a0 and "3 pallets" in a0 and a0 != a1
    edit = voice.ack({"booking": {"pallets": 3}, "items": []}, {"booking": {"pallets": 4}, "items": []}, 2)
    assert "changed from 3 to 4" in edit


def test_yes_picks_the_recommendation_without_ai():
    sess = _state_at("gross_kg")
    bridge.handle_event(sess, {"id": "y1", "type": "say", "text": "yes, use your estimate"}, today=TODAY)
    assert sess["chat"]["state"]["booking"]["gross_kg"] == 630
    bridge.handle_event(sess, {"id": "y2", "type": "say", "text": "sounds good"}, today=TODAY)
    assert sess["chat"]["state"]["booking"]["pallets"] == 2
    assert not voice.accepts_suggestion("no, it's 700 kg") and voice.accepts_suggestion("Go with your suggestion")


def test_many_details_at_once_are_summarised():
    old = {"booking": {}, "items": []}
    new = {"booking": {"seller": "Northfield", "origin_city": "London", "dest_city": "Berlin", "dest_country": "Germany",
                       "priority": "Cheapest", "ready_date": "02-11-2026"},
           "items": [{"sku": "M1", "description": "Ceramic mugs", "qty": 1080}]}
    a = voice.ack(old, new, 0)
    assert a.startswith("Nice to meet you, Northfield!") and "1,080 ceramic mugs from London to Berlin" in a
    assert a.count(",") < 8  # a summary, not a list of everything
