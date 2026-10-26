"""Serverless path: the browser holds the session and sends it with each event (JSON round trip every time)."""

import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import api_core  # noqa: E402
import bridge  # noqa: E402


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    monkeypatch.setenv("PALLET_NO_AI", "1")


class Browser:
    def __init__(self):
        self.session, self.n = None, 0
        self.payload = self.call(None)

    def call(self, ev):
        body = json.loads(json.dumps({"session": self.session, "event": ev}))  # what really goes over the wire
        out = json.loads(json.dumps(api_core.handle(body), default=str))
        self.session = out["session"]
        self.payload = out["payload"]
        return self.payload

    def send(self, type_, **kw):
        self.n += 1
        return self.call({"id": f"b{self.n}", "type": type_, **kw})


def test_first_load_gives_a_payload():
    b = Browser()
    assert b.payload["chat"]["ask"]["field"] == "dest_country"
    assert b.payload["limits"]["upload_mb"] == api_core.MAX_UPLOAD_MB


def test_full_booking_over_stateless_requests():
    b = Browser()
    answers = {"dest_country": "Germany", "dest_city": "Berlin", "ready_date": "05-11-2026", "pallets": "3",
               "gross_kg": "620", "dest_type": "Warehouse", "appointment": "Yes", "priority": "Cheapest",
               "origin_city": "London", "seller": "Northfield Goods"}
    for _ in range(30):
        ask = b.payload["chat"]["ask"]
        if ask is None:
            break
        if ask["kind"] == "item":
            b.send("item", index=ask["item_index"], fields={"description": "Mugs", "qty": "1080", "unit_price": "5",
                                                            "units_per_carton": "12", "unit_kg": "0.5",
                                                            "hs_code": "691200", "coo": "United Kingdom"})
        else:
            b.send("answer", field=ask["field"], value=answers[ask["field"]])
    r = b.payload["chat"]["result"]
    assert b.payload["chat"]["complete"] and r["recommendation"] == "Economy" and r["confirmation"]["cost"] == "£540.00"
    b.send("edit", field="pallets", value="+1")
    assert b.payload["chat"]["result"]["confirmation"]["cost"] == "£720.00"
    b.send("invoice", scope="chat")
    assert b.payload["download"]["name"].endswith(".xlsx")
    assert "download" not in b.session  # files aren't echoed back in the session


def test_example_file_fix_and_undo_survive_round_trips():
    b = Browser()
    b.send("sample")
    f = b.payload["file"]
    assert f["counts"]["total"] == 18 and f["counts"]["Blocked"] == 8
    act = next(x for x in f["results"]["BK-003"]["findings"] if x["action"])["action"]
    b.send("fix", scope="file", booking_id="BK-003", action=act)
    assert b.payload["file"]["results"]["BK-003"]["view"]["label"] == "Good to go"
    b.send("file_undo", booking_id="BK-003")
    assert b.payload["file"]["results"]["BK-003"]["view"]["label"] == "Can't ship yet"


def test_uploaded_excel_dates_survive_json():
    b = Browser()
    with open(bridge.SAMPLE_PATH, "rb") as fh:
        b.send("upload", files=[{"name": "mine.xlsx", "b64": base64.b64encode(fh.read()).decode()}])
    assert b.payload["file"]["counts"]["total"] == 18
    b.send("file_undo", booking_id="none")  # another round trip with datetimes as text
    r = b.payload["file"]["results"]["BK-014"]  # its ready date came from an Excel datetime
    assert r["view"]["label"] == "Good to go"


def test_oversized_upload_is_refused_politely():
    b = Browser()
    big = base64.b64encode(b"x" * (api_core.MAX_UPLOAD_MB * 1024 * 1024 + 10)).decode()
    b.send("upload", files=[{"name": "big.xlsx", "b64": big}])
    assert "too big" in (b.payload["flash"] or "") and b.payload["file"] is None


def test_tampered_or_broken_sessions_start_fresh():
    for bad in ("nonsense", {"chat": 5}, {"chat": {"state": {"booking": []}}}, {"chat": {"state": {}, "messages": []}}):
        out = api_core.handle({"session": bad, "event": None})
        assert out["payload"]["chat"]["ask"]["field"] == "dest_country"
    out = api_core.handle("not even a dict")
    assert out["payload"]["chat"]["messages"]


def test_vercel_handler_answers_get_and_post():
    import io
    import importlib.util
    spec = importlib.util.spec_from_file_location("event", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api", "event.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Fake(mod.handler):
        def __init__(self, method, body=b""):
            self.rfile, self.wfile = io.BytesIO(body), io.BytesIO()
            self.headers = {"Content-Length": str(len(body))}
            self.status = None
            getattr(self, f"do_{method}")()

        def send_response(self, code, message=None):
            self.status = code

        def send_header(self, *a):
            pass

        def end_headers(self):
            pass

    assert json.loads(Fake("GET").wfile.getvalue()) == {"ok": True}
    r = Fake("POST", json.dumps({"session": None, "event": None}).encode())
    assert r.status == 200 and "payload" in json.loads(r.wfile.getvalue())
