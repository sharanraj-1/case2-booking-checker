"""Vercel serverless function: POST /api/event {"session", "event"} -> {"session", "payload"}; GET = health check."""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_core  # noqa: E402

MAX_BODY = 4_400_000


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, obj: dict) -> None:
        data = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(200, {"ok": True})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._send(413, {"error": "Request too large."})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, UnicodeDecodeError):
            body = {}
        self._send(200, api_core.handle(body))
