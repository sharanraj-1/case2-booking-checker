"""Stateless request handling for serverless hosting (Vercel).

Serverless functions keep no memory between requests, so the browser holds the
session and sends it with every event: {"session": {...} | null, "event": {...} | null}.
We apply the event with the same bridge used by the Streamlit app and return
{"session": <new session>, "payload": <what the UI renders>}. The session only
contains the seller's own booking/file data, so a tampered session can only affect
that seller's view; it is size-capped and validated before use.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import bridge
from llm import client as llm_client
from llm import extract, r06

MAX_UPLOAD_MB = 3  # Vercel caps request bodies at 4.5 MB; base64 adds a third
MAX_SESSION_CHARS = 3_000_000


def _jsonable(value: Any) -> Any:
    """Make a session JSON-safe (dates -> ISO text, tuples -> lists). The engine reads these back."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _restore(raw: Any, ai_on: bool) -> dict:
    """Rebuild a session from what the browser sent; anything odd starts a fresh one."""
    fresh = bridge.new_session(ai_on)
    if not isinstance(raw, dict) or not isinstance(raw.get("chat"), dict):
        return fresh
    try:
        chat = raw["chat"]
        state = chat["state"]
        assert isinstance(state.get("booking"), dict) and isinstance(state.get("items"), list)
        assert isinstance(chat.get("messages"), list)
        sess = {**fresh, **{k: raw.get(k) for k in ("chat", "file", "last_id", "live") if k in raw}}
        sess["chat"].setdefault("turns", 0)
        sess["chat"].setdefault("last_question", "")
        state.setdefault("derived", [])
        if sess.get("file") is not None:
            f = sess["file"]
            assert isinstance(f.get("bookings"), list) and isinstance(f.get("items"), list)
            f.setdefault("notices", [])
            f.setdefault("edits", {})
        sess["ai_on"] = ai_on
        sess["flash"] = None
        sess["download"] = None
        return sess
    except (AssertionError, KeyError, TypeError, AttributeError):
        return fresh


def handle(body: Any) -> dict:
    """One request: {"session", "event"} -> {"session", "payload"}. Never raises."""
    ai_on = llm_client.available()
    body = body if isinstance(body, dict) else {}
    sess = _restore(body.get("session"), ai_on)
    ev = body.get("event")
    if isinstance(ev, dict):
        if ev.get("type") == "upload":
            total = sum(len(str(f.get("b64") or "")) for f in ev.get("files") or [] if isinstance(f, dict))
            if total * 3 / 4 > MAX_UPLOAD_MB * 1024 * 1024:
                sess["last_id"] = ev.get("id")
                sess["flash"] = f"That file is too big for the online version (limit {MAX_UPLOAD_MB} MB)."
                ev = None
        if ev is not None:
            try:
                bridge.handle_event(sess, ev, extractor=extract.extract if ai_on else None, review=r06.review)
            except Exception as e:  # never fail the request
                sess["last_id"] = ev.get("id")
                sess["flash"] = f"Sorry, something went wrong there ({type(e).__name__}). Please try again."
    try:
        payload = bridge.payload(sess, review=r06.review)
    except Exception as e:
        sess["file"] = None
        sess["flash"] = f"Sorry, that file couldn't be shown ({type(e).__name__}). Please try another file."
        payload = bridge.payload(sess, review=r06.review)
    payload["limits"]["upload_mb"] = MAX_UPLOAD_MB
    keep = {k: v for k, v in sess.items() if k not in ("download", "flash", "ai_on")}
    out_session = _jsonable(keep)
    if len(json.dumps(out_session)) > MAX_SESSION_CHARS:  # keep requests under the platform limit
        out_session["file"] = None
        payload["flash"] = "That file is too large to keep in the online version. Please split it."
    return {"session": out_session, "payload": payload}
