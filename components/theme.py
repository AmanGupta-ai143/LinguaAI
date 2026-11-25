"""Dark-mode toggle shown at the top of every page (including the sign-in page)."""
from __future__ import annotations

import streamlit as st

from services.theme import INVERT_CSS, invert_needed


def native_theme() -> str:
    """The theme Streamlit is currently showing ('light' or 'dark')."""
    try:
        theme = getattr(st.context, "theme", None)
        if theme is not None and getattr(theme, "type", None) in ("light", "dark"):
            return theme.type
    except Exception:
        pass
    return "light"


def render_theme_toggle() -> None:
    native = native_theme()
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = native == "dark"   # start in whatever the device uses
    _, right = st.columns([5, 1])
    right.toggle("🌙 Dark mode", key="dark_mode", help="Switch between light and dark")
    if invert_needed(native, st.session_state["dark_mode"]):
        st.markdown(INVERT_CSS, unsafe_allow_html=True)
