"""KPI cards and empty states."""
from __future__ import annotations

import html

import streamlit as st


def kpi_card(icon: str, value: int | str, label: str) -> None:
    shown = f"{value:,}" if isinstance(value, int) else html.escape(str(value))
    st.markdown(
        f'<div class="lg-kpi"><div class="icon">{icon}</div>'
        f'<div class="value">{shown}</div><div class="label">{html.escape(label)}</div></div>',
        unsafe_allow_html=True,
    )


def render_kpis(stats: dict) -> None:
    """Chart 4 - the four KPI cards, straight from ``DatabaseManager.get_stats``."""
    cols = st.columns(4)
    items = [
        ("🌐", stats["total_translations"], "Total translations"),
        ("🔤", stats["total_characters"], "Characters translated"),
        ("🗣️", stats["languages_used"], "Languages used"),
        ("⭐", stats["favorites"], "Favorite translations"),
    ]
    for col, (icon, value, label) in zip(cols, items):
        with col:
            kpi_card(icon, value, label)


def empty_state(title: str, message: str) -> None:
    st.markdown(
        f'<div class="lg-empty"><div class="title">{html.escape(title)}</div>'
        f"<div>{html.escape(message)}</div></div>",
        unsafe_allow_html=True,
    )
