"""Chat merge logic (pure functions, no LLM). Run: pytest tests/"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chat_state as cs  # noqa: E402
import engine  # noqa: E402

TODAY = date(2026, 10, 25)


def full_state():
    """A complete chat booking equal to the BK-001 example."""
    st = cs.new_state()
    st, changes, problems = cs.apply_patch(st, {
        "booking_updates": {"seller": "Northfield Goods", "origin_city": "london", "dest_city": "Berlin",
                            "dest_type": "a warehouse", "ready_date": "05-11-2026", "priority": "cheapest",
                            "pallets": 3, "gross_kg": "620 kg", "appointment": "yes"},
        "item_updates": [{"op": "add", "fields": {"description": "Ceramic mugs", "hs_code": "691200", "qty": 1080,
                                                  "unit_price": 5, "units_per_carton": 12, "unit_kg": 0.5,
                                                  "coo": "UK"}}],
    })
    assert not problems, problems
    return st


def check(st):
    b, items = cs.engine_input(st)
    return engine.check_booking(b, items, TODAY)


def test_defaults_origin_and_currency():
    st = cs.new_state()
    assert st["booking"]["origin_country"] == "United Kingdom" and st["booking"]["currency"] == "GBP"


def test_full_booking_is_complete_and_ready():
    st = full_state()
    assert cs.is_complete(st)
    b = st["booking"]
    assert b["dest_country"] == "Germany"  # inferred from the city
    assert b["dest_type"] == "Warehouse" and b["priority"] == "Cheapest" and b["appointment"] == "Yes"
    assert st["items"][0]["cartons"] == 90  # 1080 / 12, calculated
    assert b["cartons"] == 90 and b["declared_value"] == 5400  # calculated from items
    assert set(st["derived"]) == {"cartons", "declared_value"}
    r = check(st)
    assert r.status == "Ready" and r.recommendation == "Carrier A" and r.total_cost == 540


def test_add_item():
    st = full_state()
    st2, changes, problems = cs.apply_patch(st, {"item_updates": [
        {"op": "add", "fields": {"description": "Scented candles", "qty": 200, "unit_price": 9}}]})
    assert len(st2["items"]) == 2 and not problems
    assert any("Added item" in c for c in changes)
    assert st2["booking"]["declared_value"] == 7200  # derived total follows the items
    assert not cs.is_complete(st2)  # the new item needs HS code etc.
    assert "candles" in " ".join(cs.questions(st2)).lower()
    assert len(st["items"]) == 1  # original state not mutated


def test_update_field_and_relative_change():
    st = full_state()
    st2, changes, _ = cs.apply_patch(st, {"booking_updates": {"pallets": "+1"}})
    assert st2["booking"]["pallets"] == 4
    assert "Pallets 3 → 4" in changes
    st3, changes, _ = cs.apply_patch(st2, {"booking_updates": {"pallets": 2}})
    assert st3["booking"]["pallets"] == 2 and "Pallets 4 → 2" in changes


def test_change_pallets_rechecks_and_reports_diff():
    st = full_state()
    before = check(st)
    st2, _, _ = cs.apply_patch(st, {"booking_updates": {"pallets": 4}})
    after = check(st2)
    assert after.total_cost == 720 and before.total_cost == 540
    diff = cs.result_diff(before, after)
    assert "Cost £540.00 → £720.00" in diff
    # Overload it: 620 kg on 1 pallet excludes Carrier C (400 kg); Fastest falls back to B.
    st3, _, _ = cs.apply_patch(st, {"booking_updates": {"pallets": 1, "priority": "fastest"}})
    r = check(st3)
    assert r.recommendation == "Carrier B" and r.rule_status["R-05"] == "Pass"


def test_remove_item_by_description_word():
    st = full_state()
    st, _, _ = cs.apply_patch(st, {"item_updates": [
        {"op": "add", "fields": {"description": "Scented candles", "qty": 200, "unit_price": 9}}]})
    st2, changes, problems = cs.apply_patch(st, {"item_updates": [
        {"op": "remove", "match_sku_or_index": "the candles", "fields": {}}]})
    assert not problems and len(st2["items"]) == 1 and st2["items"][0]["description"] == "Ceramic mugs"
    assert any("Removed item: Scented candles" in c for c in changes)
    assert st2["booking"]["declared_value"] == 5400


def test_update_item_by_number_and_sku():
    st = full_state()
    st2, changes, _ = cs.apply_patch(st, {"item_updates": [
        {"op": "update", "match_sku_or_index": 1, "fields": {"qty": 1200}}]})
    it = st2["items"][0]
    assert it["qty"] == 1200 and it["cartons"] == 100  # derived cartons follow
    assert st2["booking"]["cartons"] == 100 and st2["booking"]["declared_value"] == 6000
    sku = it["sku"]
    st3, _, _ = cs.apply_patch(st2, {"item_updates": [
        {"op": "update", "match_sku_or_index": sku, "fields": {"unit_price": 4}}]})
    assert st3["items"][0]["unit_price"] == 4


def test_stated_totals_are_not_overwritten():
    st = full_state()
    st2, _, _ = cs.apply_patch(st, {"booking_updates": {"cartons": 100}})
    assert st2["booking"]["cartons"] == 100 and "cartons" not in st2["derived"]
    assert check(st2).rule_status["R-04"] == "Red"  # seller said 100, items make 90
    st3, _, _ = cs.apply_patch(st2, {"item_updates": [{"op": "update", "match_sku_or_index": 1, "fields": {"qty": 1320}}]})
    assert st3["items"][0]["cartons"] == 110
    assert st3["booking"]["cartons"] == 100  # seller's number kept, not recalculated
    assert check(st3).rule_status["R-04"] == "Red"


def test_make_it_lyon_switches_country():
    st = full_state()
    st2, changes, problems = cs.apply_patch(st, {"booking_updates": {"dest_city": "Lyon"}})
    assert not problems
    assert st2["booking"]["dest_city"] == "Lyon" and st2["booking"]["dest_country"] == "France"
    assert check(st2).total_cost == 510  # 3 x £170


def test_conflicting_city_and_country_is_asked_not_guessed():
    st = cs.new_state()
    st2, _, problems = cs.apply_patch(st, {"booking_updates": {"dest_city": "Lyon", "dest_country": "Germany"}})
    assert "dest_city" not in st2["booking"] and problems and "Lyon is in France" in problems[0]


def test_germany_without_city_asks_with_options():
    st, _, _ = cs.apply_patch(cs.new_state(), {"booking_updates": {"dest_country": "germany"}})
    qs = " ".join(cs.questions(st))
    assert "Berlin, Frankfurt, Hamburg" in qs


def test_synonyms():
    st, _, problems = cs.apply_patch(cs.new_state(), {"booking_updates": {
        "dest_city": "Frankfurt am Main", "dest_type": "a shop", "priority": "cheapest", "appointment": "no"}})
    b = st["booking"]
    assert not problems
    assert (b["dest_city"], b["dest_type"], b["priority"], b["appointment"]) == \
        ("Frankfurt", "Business address", "Cheapest", "No")


def test_invalid_values_are_rejected_with_options():
    st, _, problems = cs.apply_patch(cs.new_state(), {"booking_updates": {
        "dest_city": "Munich", "origin_city": "Glasgow", "pallets": "three", "ready_date": "32-13-2026"}})
    text = " ".join(problems)
    assert "Munich" in text and "Glasgow" in text and "London" in text
    assert "'three'" in text and "DD-MM-YYYY" in text
    for k in ("dest_city", "origin_city", "pallets", "ready_date"):
        assert k not in st["booking"]


def test_past_date_is_kept_but_questioned():
    st, _, problems = cs.apply_patch(cs.new_state(), {"booking_updates": {"ready_date": "01-01-2020"}})
    assert st["booking"]["ready_date"] == "01-01-2020" and "in the past" in problems[0]


def test_asks_only_missing_one_or_two_at_a_time():
    st, _, _ = cs.apply_patch(cs.new_state(), {
        "booking_updates": {"dest_country": "Germany"},
        "item_updates": [{"op": "add", "fields": {"description": "mugs"}}]})
    qs = cs.questions(st)
    assert 1 <= len(qs) <= 2
    assert not any("Germany, France" in q for q in qs)  # country already known
    assert "dest_country" not in cs.missing_fields(st)


def test_business_address_needs_no_appointment():
    st, _, _ = cs.apply_patch(cs.new_state(), {"booking_updates": {"dest_type": "Business address"}})
    assert "appointment" not in cs.missing_fields(st)
    st, _, _ = cs.apply_patch(cs.new_state(), {"booking_updates": {"dest_type": "Warehouse"}})
    assert "appointment" in cs.missing_fields(st)


def test_bad_patch_shapes_never_crash():
    st = full_state()
    for patch in (None, {}, {"booking_updates": "x"}, {"item_updates": "x"}, {"item_updates": [1, None, {"op": "zap"}]},
                  {"item_updates": [{"op": "update", "match_sku_or_index": "nothing like it", "fields": {"qty": 1}}]},
                  {"booking_updates": {"pallets": "+1", "unknown": 5}}):
        cs.apply_patch(st, patch)


def test_apply_fix_action_from_engine():
    st = full_state()
    st, _, _ = cs.apply_patch(st, {"booking_updates": {"declared_value": 5000}})
    r = check(st)
    f = next(f for f in r.findings if f.rule_id == "R-02")
    st2, changes, _ = cs.apply_fix_action(st, f.fix_action)
    assert st2["booking"]["declared_value"] == 5400 and check(st2).rule_status["R-02"] == "Pass"


def test_reply_never_reasks_known_fields():
    st = full_state()
    reply = cs.build_reply(st, ["Pallets 3 → 4"], [])
    assert "Confirm booking" in reply and "?" not in reply


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
