"""Tests for engine.py. Run: python test_engine.py   (or: pytest)"""

import io
import os
import sys
from collections import Counter
from datetime import date, datetime

import engine

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "test_bookings.xlsx")
TODAY = date(2026, 10, 25)

# booking_id -> (findings as Counter of (rule, severity), status, carrier, total cost)
EXPECTED = {
    "BK-001": ({}, "Ready", "Carrier A", 540),
    "BK-002": ({("R-01", "Red"): 3}, "Blocked", "Carrier A", 170),
    "BK-003": ({("R-02", "Red"): 1}, "Blocked", "Carrier A", 360),
    "BK-004": ({}, "Ready", "Carrier A", 160),
    "BK-005": ({("R-03", "Red"): 1}, "Blocked", "Carrier C", 340),
    "BK-006": ({("R-04", "Red"): 1}, "Blocked", "Carrier C", 640),
    "BK-007": ({("R-05", "Red"): 1}, "Blocked", "Carrier B", 880),
    "BK-008": ({}, "Ready", "Carrier B", 420),
    "BK-009": ({("R-06", "Red"): 2}, "Blocked", "Carrier A", 180),
    "BK-010": ({("R-07", "Amber"): 1}, "Ready with warnings", "Carrier C", 330),
    "BK-011": ({("R-08", "Amber"): 1}, "Ready with warnings", "Carrier B", 200),
    "BK-012": ({("R-09", "Amber"): 1}, "Ready with warnings", "Carrier A", 170),
    "BK-013": ({("R-10", "Amber"): 1}, "Ready with warnings", "Carrier B", 220),
    "BK-014": ({}, "Ready", "Carrier B", 420),
    "BK-015": ({}, "Ready", "Carrier C", 320),
    "BK-016": ({("R-06", "Advisory"): 1}, "Ready", "Carrier A", 180),
    "BK-017": ({("R-05", "Red"): 1}, "Blocked", "Carrier A", 180),
    "BK-018": ({("R-04", "Data"): 1}, "Blocked", "Carrier A", 170),
}


def _sample():
    if not os.path.exists(SAMPLE):
        import make_test_file
        make_test_file.write(SAMPLE)
    return engine.load_workbook(SAMPLE)


def _results():
    bookings, items, notices = _sample()
    return {r.booking_id: r for r in engine.check_all(bookings, items, TODAY, notices)}, notices


# --- Sample file: one planted mistake per rule --------------------------------

def test_sample_file_matches_expected():
    results, _ = _results()
    assert set(results) == set(EXPECTED), sorted(results)
    for bid, (findings, status, carrier, cost) in EXPECTED.items():
        r = results[bid]
        got = Counter((f.rule_id, f.severity) for f in r.findings)
        assert got == Counter(findings), f"{bid}: {got} != {findings}\n" + "\n".join(f.message for f in r.findings)
        assert r.status == status, f"{bid}: status {r.status}"
        assert r.recommendation == carrier, f"{bid}: carrier {r.recommendation} ({r.reason})"
        assert r.total_cost == cost, f"{bid}: cost {r.total_cost}"
        assert r.reason, bid


def test_every_rule_is_caught_once_in_sample():
    results, _ = _results()
    caught = {f.rule_id for r in results.values() for f in r.findings if f.severity in ("Red", "Amber")}
    assert caught == set(engine.RULE_IDS), caught


def test_every_finding_has_a_fix():
    results, _ = _results()
    for r in results.values():
        for f in r.findings:
            assert f.message and f.fix, (r.booking_id, f)


def test_example_row_bk001():
    results, _ = _results()
    r = results["BK-001"]
    assert r.rules_passed == engine.RULE_IDS
    assert round(r.weight_per_pallet) == 207
    costs = {o.carrier: o.cost for o in r.options}
    assert costs == {"Carrier A": 540, "Carrier B": 660, "Carrier C": 1020}
    assert r.collection_date == date(2026, 11, 5)
    assert r.eta == date(2026, 11, 12)  # 5 working days (Thu -> Thu)


def test_loader_notices_and_traps():
    bookings, items, notices = _sample()
    msgs = " ".join(n["message"] for n in notices)
    assert "BK-099" in msgs and "ZZ-ORPHAN" in msgs  # orphan item
    assert len(bookings) == 18  # blank row skipped, example row kept
    tea = next(i for i in items if i["sku"] == "TT-TEA")
    assert tea["hs_code"] == "090210"  # text keeps its leading zero
    pepper = next(i for i in items if i["sku"] == "SC-PEP")
    assert pepper["hs_code"] == "90412"


def test_r01_leading_zero_note_and_fix():
    results, _ = _results()
    f = next(f for f in results["BK-002"].findings if f.sku == "SC-PEP")
    assert "leading zero" in f.fix and "090412" in f.fix
    assert f.fix_action["value"] == "090412"


def test_r02_message_has_numbers_and_gap():
    results, _ = _results()
    f = results["BK-003"].findings[0]
    assert "£5,700.00" in f.message and "£6,000.00" in f.message and "5.0%" in f.message
    assert f.fix_action == {"target": "booking", "field": "declared_value", "value": 6000.0}


def test_r03_offers_both_fixes_and_whole_number_note():
    results, _ = _results()
    f = results["BK-005"].findings[0]
    assert "quantity to 240" in f.fix and "not a whole number" in f.fix


def test_r05_none_fit_lists_pallets_per_carrier():
    results, _ = _results()
    r = results["BK-007"]
    f = r.findings[0]
    assert "800 kg per pallet" in f.message
    for text in ("Carrier B needs 4 pallets (£880.00)", "Carrier A needs 5 pallets (£900.00)",
                 "Carrier C needs 6 pallets (£2,040.00)"):
        assert text in f.fix, f.fix
    assert f.fix_action["value"] == 4


def test_r05_450kg_fastest_falls_back_to_b():
    results, _ = _results()
    r = results["BK-008"]
    c = next(o for o in r.options if o.carrier == "Carrier C")
    assert c.eligible is False and "400 kg limit" in c.excluded_reason
    assert "Carrier C excluded" in r.reason


def test_r06_keyword_screen():
    red = ["Power bank 10000mAh", "Perfume 50ml", "Li-ion battery pack", "Hairspray 300ml",
           "Deodorant spray", "Spray paint red", "Nail polish set", "Lighter fluid", "Hand sanitiser 500ml",
           "Disposable vape", "Bluetooth speaker", "Rechargeable torch", "Paint thinners"]
    clean = ["Battery-free kitchen timer", "Alcohol-free toner", "Non-aerosol hair gel", "Scented soy candle",
             "Ceramic coffee mug", "Ginger biscuits", "Petroleum jelly"]
    ambiguous = ["Wireless mouse", "AA batteries", "Kitchen cleaning spray", "Cosmetics bag"]
    for d in red:
        assert engine.dg_screen(d) and engine.dg_screen(d)[0] == "red", d
    for d in clean:
        assert engine.dg_screen(d) is None, (d, engine.dg_screen(d))
    for d in ambiguous:
        assert engine.dg_screen(d) and engine.dg_screen(d)[0] == "ambiguous", d


def test_r06_shows_triggering_phrase():
    results, _ = _results()
    msgs = [f.message for f in results["BK-009"].findings]
    assert any("'power bank'" in m for m in msgs) and any("'perfume'" in m for m in msgs)


def test_r07_states_missing_kg():
    results, _ = _results()
    assert "40 kg less" in results["BK-010"].findings[0].message


def test_r10_today_is_not_past_and_dates_are_ddmmyyyy():
    assert engine.parse_date("05-11-2026") == date(2026, 11, 5)
    assert engine.parse_date("5/11/2026") == date(2026, 11, 5)
    assert engine.parse_date(datetime(2026, 11, 5, 0, 0)) == date(2026, 11, 5)
    assert engine.parse_date("2026-11-05 00:00:00") == date(2026, 11, 5)
    assert engine.parse_date("31-02-2026") is None
    base = _clean_booking()
    r = engine.check_booking({**base[0], "ready_date": "25-10-2026"}, base[1], TODAY)
    assert r.rule_status["R-10"] == "Pass"
    r = engine.check_booking({**base[0], "ready_date": "24-10-2026"}, base[1], TODAY)
    assert r.rule_status["R-10"] == "Amber"


def _clean_booking():
    b = dict(booking_id="T-1", seller="Test Ltd", origin_city="London", origin_country="United Kingdom",
             dest_city="Berlin", dest_country="Germany", dest_type="Warehouse", ready_date="05-11-2026",
             priority="Cheapest", pallets=3, cartons=90, declared_value=5400, currency="GBP", gross_kg=620,
             appointment="Yes")
    items = [dict(sku="M1", description="Mug", hs_code="691200", qty=1080, unit_price=5, units_per_carton=12,
                  cartons=90, unit_kg=0.5, coo="United Kingdom")]
    return b, items


def test_r02_tolerance_boundary():
    b, items = _clean_booking()
    assert engine.check_booking({**b, "declared_value": 5400 * 1.008}, items, TODAY).rule_status["R-02"] == "Pass"
    assert engine.check_booking({**b, "declared_value": 5400 * 1.0101}, items, TODAY).rule_status["R-02"] == "Red"
    assert engine.check_booking({**b, "declared_value": 5400 * 1.01}, items, TODAY).rule_status["R-02"] == "Pass"


def test_balanced_uses_minimax_regret_not_equal_weight():
    b, items = _clean_booking()
    for country, city in (("Germany", "Berlin"), ("France", "Paris"), ("Netherlands", "Amsterdam")):
        r = engine.check_booking({**b, "priority": "Balanced", "dest_country": country, "dest_city": city}, items, TODAY)
        assert r.recommendation == "Carrier B", (country, r.reason)
        assert "never the priciest, slowest or least reliable" in r.reason


def test_weight_bands():
    b, items = _clean_booking()
    items = [{**items[0], "unit_kg": 0.1}]
    cases = [(1200, "Cheapest", "Carrier A"), (1200, "Fastest", "Carrier C"), (1200, "Most reliable", "Carrier C"),
             (1350, "Fastest", "Carrier B"), (1350, "Most reliable", "Carrier B"), (1350, "Cheapest", "Carrier A"),
             (1800, "Cheapest", "Carrier B"), (1800, "Fastest", "Carrier B")]
    for gross, prio, want in cases:  # 3 pallets -> 400 / 450 / 600 kg per pallet
        r = engine.check_booking({**b, "gross_kg": gross, "priority": prio}, items, TODAY)
        assert r.recommendation == want, (gross, prio, r.recommendation, r.reason)
        assert r.rule_status["R-05"] == "Pass"


def test_pallets_zero_is_handled():
    b, items = _clean_booking()
    r = engine.check_booking({**b, "pallets": 0}, items, TODAY)
    assert r.rule_status["R-05"] == "Red" and r.status == "Blocked"


def test_bad_values_never_crash():
    weird = [
        {}, {"booking_id": "X", "pallets": "three", "gross_kg": "lots", "ready_date": "soon"},
        {"booking_id": "Y", "dest_country": "Spain", "dest_city": "Madrid", "priority": "whatever"},
        {"booking_id": "Z", "dest_country": "Germany", "dest_city": "Lyon", "currency": "EUR"},
    ]
    for b in weird:
        r = engine.check_booking(b, [{"description": None, "qty": "x", "hs_code": 12.0}], TODAY)
        assert r.status == "Blocked"
    r = engine.check_booking({"dest_country": "Germany", "dest_city": "Lyon"}, [], TODAY)
    assert any("Lyon is in France" in f.message for f in r.findings)


def test_csv_loader_and_bad_file():
    b_csv = io.BytesIO("Title\nBooking ID,Seller name,Pallets\nBK-1,Acme,2\n".encode())
    i_csv = io.BytesIO("Booking ID,SKU,HS code\nBK-1,S1,012345\n".encode())
    bookings, items, notices = engine.load_csvs(b_csv, i_csv)
    assert bookings[0]["pallets"] == 2 and items[0]["hs_code"] == "012345"
    assert any("missing column" in n["message"] for n in notices)
    _, _, notices = engine.load_workbook(io.BytesIO(b"not an excel file"))
    assert notices and notices[0]["level"] == "error"


def test_ai_review_yes_adds_red_and_no_keeps_keyword_findings():
    results, _ = _results()
    r = results["BK-016"]  # "Wireless mouse": advisory only
    flagged = engine.apply_ai_review(r, {"Wireless mouse": {"contains_dg": "yes", "category": "lithium battery", "why": "x"}})
    assert flagged.status == "Blocked" and r.status == "Ready"  # original untouched
    assert any(f.severity == "Red" and f.message.startswith("Flagged by AI review") for f in flagged.findings)
    safe = engine.apply_ai_review(r, {"Wireless mouse": {"contains_dg": "no", "category": "none", "why": "AA cells"}})
    assert safe.status == "Ready" and len(safe.findings) == len(r.findings)
    assert safe.findings[0].meta["ai"]["contains_dg"] == "no"


def test_duplicate_ids_are_flagged():
    bookings = [{"booking_id": "A1", "_row": 4}, {"booking_id": "a1", "_row": 5}]
    bookings, _, notices = engine._finalise(bookings, [], [])
    assert "duplicate" in bookings[1]["booking_id"] and notices


# --- Runner -------------------------------------------------------------------

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
