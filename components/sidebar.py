"""Shared page setup: CSS, sidebar branding, footer."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from services.translator import LANGUAGES

ASSETS = Path(__file__).resolve().parent.parent / "assets"
LOGO = ASSETS / "logo.png"


def _on_search() -> None:
    """Enter pressed in the sidebar search box -> remember the query and open the Search page."""
    query = st.session_state.get("global_q", "").strip()
    if query:
        st.session_state["search_q"] = query
        st.session_state["_goto_search"] = True


def load_css() -> None:
    css = (ASSETS / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_sidebar() -> None:
    if LOGO.exists():
        st.logo(str(LOGO), size="large")
    with st.sidebar:
        st.markdown(
            '<div class="lg-brand"><div class="mark">LA</div><div class="name">LinguaAI</div></div>',
            unsafe_allow_html=True,
        )
        st.caption("Smart Language Translation Platform")
        st.text_input(
            "Search", key="global_q", placeholder="🔍 Search history & favorites",
            label_visibility="collapsed", on_change=_on_search,
        )
        st.divider()
        st.caption(f"{len(LANGUAGES)} languages supported")
        st.caption("Theme: follows your device. Change it in ⋮ → Settings → Theme.")


def page_header(title: str, subtitle: str, chips: list[str] | None = None) -> None:
    chips_html = ""
    if chips:
        chips_html = '<div class="lg-chips">' + "".join(f'<span class="lg-chip">{c}</span>' for c in chips) + "</div>"
    st.markdown(
        f'<div class="lg-hero"><h1>{title}</h1><p>{subtitle}</p>{chips_html}</div>',
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        '<div class="lg-footer"><b>LinguaAI</b> - Smart Language Translation Platform<br>'
        "Built with Python, Streamlit and the MyMemory Translation API.</div>",
        unsafe_allow_html=True,
    )
