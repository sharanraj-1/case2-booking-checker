"""app.py starts cleanly with no API key, and the built front end is present."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def test_app_runs_without_key(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(ROOT)
    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=60).run()
    assert not at.exception, at.exception
    assert "sess" in at.session_state


def test_frontend_is_built():
    dist = os.path.join(ROOT, "pallet_ui", "frontend", "dist")
    assert os.path.exists(os.path.join(dist, "index.html")), "run `npm run build` in pallet_ui/frontend"
    assets = os.listdir(os.path.join(dist, "assets"))
    assert any(a.endswith(".js") for a in assets) and any(a.endswith(".css") for a in assets)
