"""The React front end as a Streamlit custom component.

Release: serves the built files in frontend/dist (commit them; Streamlit Cloud has no Node).
Development: set PALLET_UI_DEV=1 and run `npm run dev` in frontend/ for hot reload.
"""

import os

import streamlit.components.v1 as components

_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")

if os.environ.get("PALLET_UI_DEV"):
    _component = components.declare_component("pallet_ui", url="http://localhost:5173")
else:
    _component = components.declare_component("pallet_ui", path=_DIST)


def pallet_ui(payload: dict, key: str, on_change=None):
    """Render the app. Returns the latest UI event dict (also in st.session_state[key])."""
    return _component(payload=payload, key=key, default=None, on_change=on_change)
