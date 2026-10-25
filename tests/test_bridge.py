"""Bridge: UI events -> engine -> payload. No Streamlit, no LLM."""

import base64
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge  # noqa: E402

TODAY = date(2026, 10, 25)
_n = 0


def ev(type_, **kw):
    global _n
    _n += 1
    return {"id": f"e{_n}", "type": type_, **kw}


def send(sess, e, **kw):
    return bridge.handle_event(sess, e, today=TODAY, **kw)


def walk_no_ai(sess):
    """Answer every question the way a person would, using only the structured asks."""
    answers = {"dest_country": "Germany", "dest_city": "Berlin", "ready_date": "05-11-2026", "pallets": "3",
               "gross_kg": "620", "dest_type": "Warehouse", "appointment": "Yes", "priority": "Cheapest",
               "origin_city": "London", "seller": "Northfield Goods"}
    for _ in range(30):
        ask = bridge.next_ask(sess["chat"]["state"])
        if ask is None:
            return
        if ask["kind"] == "item":
            send(sess, ev("item", index=ask["item_index"], fields={
                "description": "Ceramic mugs", "qty": "1080", "unit_price": "5", "units_per_carton": "12",
                "unit_kg": "0.5", "hs_code": "691200", "coo": "United Kingdom"}))
        else:
            send(sess, ev("answer", field=ask["field"], value=answers[ask["field"]]))
    raise AssertionError("conversation didn't finish")


def test_no_ai_conversation_reaches_ready_and_confirms():
    sess = bridge.new_session(ai_on=False)
    p = bridge.payload(sess, today=TODAY)
    assert p["chat"]["ask"]["field"] == "dest_country" and len(p["chat"]["ask"]["options"]) == 3
    walk_no_ai(sess)
    p = bridge.payload(sess, today=TODAY)
    chat = p["chat"]
    assert chat["complete"] and chat["ask"] is None
    r = chat["result"]
    assert r["view"]["label"] == "Good to go" and r["recommendation"] == "Economy"
    assert r["confirmation"]["cost"] == "£540.00"
    send(sess, ev("confirm"))
    assert bridge.payload(sess, today=TODAY)["chat"]["confirmed"]
    json.dumps(p)  # everything the UI gets must be JSON


def test_typed_answers_without_ai_go_to_the_asked_field():
    sess = bridge.new_session()
    send(sess, ev("say", text="germany"))
    assert sess["chat"]["state"]["booking"]["dest_country"] == "Germany"
    send(sess, ev("say", text="Frankfurt am Main"))
    assert sess["chat"]["state"]["booking"]["dest_city"] == "Frankfurt"



def test_invalid_typed_value_explains_options():
    sess = bridge.new_session()
    send(sess, ev("answer", field="dest_city", value="Munich"))
    text = sess["chat"]["messages"][-1]["text"]
    assert "Munich" in text and "Frankfurt" in text and "300 km" in text  # closest served city suggested


def test_edit_pallets_shows_change_and_effect():
    sess = bridge.new_session()
    walk_no_ai(sess)
    send(sess, ev("edit", field="pallets", value="+1"))
    msg = sess["chat"]["messages"][-1]
    assert "Pallets 3 → 4" in msg["changes"] and "Cost £540.00 → £720.00" in msg["effects"]
    assert not sess["chat"]["state"]["confirmed"]


def test_remove_and_update_items():
    sess = bridge.new_session()
    walk_no_ai(sess)
    send(sess, ev("item", index=None, fields={"description": "Candles", "qty": 200, "unit_price": 9}))
    assert len(sess["chat"]["state"]["items"]) == 2
    ask = bridge.next_ask(sess["chat"]["state"])
    assert ask["kind"] == "item" and ask["item_index"] == 1 and "hs_code" in ask["missing"]
    send(sess, ev("remove_item", index=1))
    assert len(sess["chat"]["state"]["items"]) == 1
    send(sess, ev("item", index=0, fields={"qty": 1200}))
    assert sess["chat"]["state"]["items"][0]["cartons"] == 100


def test_fix_button_in_chat():
    sess = bridge.new_session()
    walk_no_ai(sess)
    send(sess, ev("edit", field="declared_value", value="5000"))
    r = bridge.payload(sess, today=TODAY)["chat"]["result"]
    f = next(f for f in r["findings"] if f["rule"] == "R-02")
    assert f["action_label"] == "Set total declared value to £5,400.00"
    send(sess, ev("fix", scope="chat", action=f["action"]))
    assert bridge.payload(sess, today=TODAY)["chat"]["result"]["view"]["label"] == "Good to go"


def test_duplicate_event_ids_are_ignored():
    sess = bridge.new_session()
    e = ev("answer", field="pallets", value="+1")
    send(sess, ev("answer", field="pallets", value="2"))
    send(sess, e)
    send(sess, e)
    assert sess["chat"]["state"]["booking"]["pallets"] == 3


def test_extractor_used_when_available_and_failure_falls_back():
    sess = bridge.new_session(ai_on=True)
    send(sess, ev("say", text="3 pallets to Lyon"),
         extractor=lambda t, s, q: {"booking_updates": {"pallets": 3, "dest_city": "Lyon"}, "item_updates": []})
    b = sess["chat"]["state"]["booking"]
    assert b["pallets"] == 3 and b["dest_country"] == "France"
    send(sess, ev("say", text="hello"), extractor=lambda t, s, q: None)  # AI down; no field fits "hello"
    assert sess["chat"]["messages"][-1]["role"] == "assistant"


def test_sample_and_upload_and_file_fix():
    sess = bridge.new_session()
    send(sess, ev("sample"))
    p = bridge.payload(sess, today=TODAY)["file"]
    assert p["counts"]["total"] == 18 and p["counts"]["Blocked"] == 8 and p["xlsx"]
    r = p["results"]["BK-003"]
    act = next(f for f in r["findings"] if f["action"])["action"]
    send(sess, ev("fix", scope="file", booking_id="BK-003", action=act))
    p = bridge.payload(sess, today=TODAY)["file"]
    assert p["results"]["BK-003"]["view"]["label"] == "Good to go"
    assert next(x for x in p["rows"] if x["id"] == "BK-003")["edited"]
    send(sess, ev("file_undo", booking_id="BK-003"))
    assert bridge.payload(sess, today=TODAY)["file"]["results"]["BK-003"]["view"]["label"] == "Can't ship yet"
    with open(bridge.SAMPLE_PATH, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    send(sess, ev("upload", files=[{"name": "mine.xlsx", "b64": b64}]))
    assert bridge.payload(sess, today=TODAY)["file"]["counts"]["total"] == 18


def test_bad_uploads_never_crash():
    sess = bridge.new_session()
    for files in ([{"name": "x.xlsx", "b64": base64.b64encode(b"garbage").decode()}],
                  [{"name": "x.pdf", "b64": ""}], [{"name": "x.xlsx", "b64": "!!notbase64"}], []):
        send(sess, ev("upload", files=files))
        p = bridge.payload(sess, today=TODAY)
        json.dumps(p)


def test_every_sample_booking_serialises_with_plain_language():
    sess = bridge.new_session()
    send(sess, ev("sample"))
    p = bridge.payload(sess, today=TODAY)["file"]
    for bid, r in p["results"].items():
        assert r["view"]["label"] in ("Can't ship yet", "OK to ship", "Good to go")
        assert r["recommendation"] and r["confirmation"]["route"] and r["next_steps"]
        assert len(r["rules"]) == 10
