"""Thin Anthropic client: one JSON-returning call with safe parsing and one retry."""

from __future__ import annotations

import json
import re
from typing import Any

from llm import config

_client = None
_client_key = None
last_error: str | None = None  # shown in the UI when the AI is unavailable


def get_client():
    """Return an Anthropic client, or None if there's no key or the SDK is missing."""
    global _client, _client_key
    key = config.get_api_key()
    if not key:
        return None
    if _client is None or key != _client_key:
        try:
            import anthropic
            _client = anthropic.Anthropic(api_key=key, timeout=config.TIMEOUT_SECONDS, max_retries=1)
            _client_key = key
        except Exception:
            return None
    return _client


def available() -> bool:
    return get_client() is not None


def parse_json(text: str | None) -> dict | None:
    """Strip ```json fences and surrounding prose, then parse the first JSON object."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I | re.M).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(t[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _create(client, system: str, messages: list[dict]):
    import anthropic
    kwargs = dict(model=config.MODEL, max_tokens=config.MAX_TOKENS, system=system, messages=messages,
                  output_config={"effort": config.EFFORT})
    try:
        return client.beta.messages.create(**kwargs, betas=[config.FALLBACK_BETA], fallbacks="default")
    except anthropic.BadRequestError:
        # Account or region without the fallback beta: plain request.
        return client.messages.create(**kwargs)


def _text(resp) -> str:
    return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")


def call_json(system: str, user: str) -> dict | None:
    """Ask for a JSON object. Retries once on unparseable output. Returns None on any failure."""
    global last_error
    client = get_client()
    if client is None:
        last_error = "No API key configured."
        return None
    import anthropic
    messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
    for attempt in range(2):
        try:
            resp = _create(client, system, messages)
        except anthropic.AuthenticationError:
            last_error = "The API key was rejected."
            return None
        except anthropic.RateLimitError:
            last_error = "The AI service is busy (rate limited)."
            return None
        except anthropic.APIStatusError as e:
            last_error = f"The AI service returned an error ({e.status_code})."
            return None
        except anthropic.APIConnectionError:
            last_error = "Couldn't reach the AI service."
            return None
        except Exception as e:  # never let the AI break the app
            last_error = f"AI call failed ({type(e).__name__})."
            return None
        if getattr(resp, "stop_reason", None) == "refusal":
            last_error = "The AI declined this request."
            return None
        text = _text(resp)
        obj = parse_json(text)
        if obj is not None:
            last_error = None
            return obj
        # Retry as a fresh single-turn request (no edited history), with a firmer instruction.
        messages = [{"role": "user", "content": user + "\n\nIMPORTANT: reply with only one valid JSON object and no other text."}]
    last_error = "The AI reply couldn't be read."
    return None
