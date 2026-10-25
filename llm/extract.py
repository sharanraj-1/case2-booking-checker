"""Chat extraction: seller message -> patch for chat_state.apply_patch()."""

from __future__ import annotations

import engine
from llm import client, prompts


def extract(message: str, state: dict, last_question: str = "") -> dict | None:
    """Return a patch dict, or None if the AI is unavailable or replied badly."""
    user = prompts.extract_user(message, state["booking"], state["items"], last_question,
                                engine.format_date(engine.today_london()))
    obj = client.call_json(prompts.EXTRACT_SYSTEM, user)
    if obj is None:
        return None
    patch = {
        "booking_updates": obj.get("booking_updates") if isinstance(obj.get("booking_updates"), dict) else {},
        "item_updates": [u for u in (obj.get("item_updates") or []) if isinstance(u, dict)]
        if isinstance(obj.get("item_updates"), list) else [],
        "reply_hint": obj.get("reply_hint") if isinstance(obj.get("reply_hint"), str) else "",
    }
    # Origin country and currency are fixed; ignore anything else the model sent for them.
    patch["booking_updates"].pop("origin_country", None)
    patch["booking_updates"].pop("currency", None)
    return patch
