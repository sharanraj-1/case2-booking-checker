"""Run the Vercel version locally: static React build + /api/event, no Streamlit. python dev_server.py [port]"""

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import api_core

DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pallet_ui", "frontend", "dist")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIST, **kw)

    def _json(self, obj):
        data = json.dumps(obj, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/event"):
            return self._json({"ok": True})
        return super().do_GET()

    def do_POST(self):
        if not self.path.startswith("/api/event"):
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            parsed = json.loads(body or b"{}")
        except ValueError:
            parsed = {}
        self._json(api_core.handle(parsed))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8600
    print(f"Pallet Pre-Flight (Vercel mode) on http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
