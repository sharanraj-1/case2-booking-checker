"""Thin OpenRouter client: one JSON-returning call with safe parsing and one retry."""

from __future__ import annotations

import json
import re

import requests

from llm import config

last_error: str | None = None  # shown in the UI when the AI is unavailable


def available() -> bool:
    return bool(config.get_api_key())


def parse_json(text: str | None) -> dict | None:
    """Strip ```json fences and surrounding prose, then parse the first JSON object."""
    if not text:
        return None
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.M).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(t[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _post(key: str, system: str, user: str) -> requests.Response:
    return requests.post(
        config.BASE_URL, timeout=config.TIMEOUT_SECONDS,
        headers={"Authorization": f"Bearer {key}", "X-Title": config.APP_TITLE,
                 "HTTP-Referer": "https://github.com/pallet-preflight"},
        json={"model": config.MODEL, "max_tokens": config.MAX_TOKENS,
              "reasoning": {"effort": config.REASONING_EFFORT},
              "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})


def call_json(system: str, user: str) -> dict | None:
    """Ask for a JSON object. Retries once on unparseable output. Returns None on any failure."""
    global last_error
    key = config.get_api_key()
    if not key:
        last_error = "No API key configured."
        return None
    for attempt in range(2):
        try:
            r = _post(key, system, user if attempt == 0 else
                      user + "\n\nIMPORTANT: reply with only one valid JSON object and no other text.")
        except requests.Timeout:
            last_error = "The AI service took too long to answer."
            return None
        except requests.RequestException:
            last_error = "Couldn't reach the AI service."
            return None
        if r.status_code == 401:
            last_error = "The API key was rejected."
            return None
        if r.status_code == 402:
            last_error = "The AI account is out of credit."
            return None
        if r.status_code == 429:
            last_error = "The AI service is busy (rate limited)."
            return None
        if r.status_code >= 400:
            last_error = f"The AI service returned an error ({r.status_code})."
            return None
        try:
            choice = r.json()["choices"][0]
            text = (choice.get("message") or {}).get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError):
            text = ""
        obj = parse_json(text)
        if obj is not None:
            last_error = None
            return obj
    last_error = "The AI reply couldn't be read."
    return None
