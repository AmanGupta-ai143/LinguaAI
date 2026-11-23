"""KPI cards, onboarding card and empty states."""
from __future__ import annotations

import html

import streamlit as st


def kpi_card(icon: str, value: int | str, label: str, sub: str = "", tone: str = "blue") -> None:
    shown = f"{value:,}" if isinstance(value, int) else html.escape(str(value))
    sub_html = f'<div class="sub">{html.escape(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="lg-kpi {tone}"><div class="badge">{icon}</div>'
        f'<div class="value">{shown}</div><div class="label">{html.escape(label)}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def render_kpis(stats: dict, subs: dict | None = None) -> None:
    """Chart 4 - the four KPI cards, straight from ``DatabaseManager.get_stats``.

    ``subs`` optionally carries small captions (all derived from real records).
    """
    subs = subs or {}
    cols = st.columns(4)
    items = [
        ("🌐", stats["total_translations"], "Total translations", subs.get("total", ""), "blue"),
        ("🔤", stats["total_characters"], "Characters translated", subs.get("chars", ""), "purple"),
        ("🗣️", stats["languages_used"], "Languages used", subs.get("languages", ""), "teal"),
        ("⭐", stats["favorites"], "Favorite translations", subs.get("favorites", ""), "amber"),
    ]
    for col, (icon, value, label, sub, tone) in zip(cols, items):
        with col:
            kpi_card(icon, value, label, sub, tone)


def empty_state(title: str, message: str, icon: str = "📊") -> None:
    st.markdown(
        f'<div class="lg-empty"><div class="icon">{icon}</div><div class="title">{html.escape(title)}</div>'
        f"<div>{html.escape(message)}</div></div>",
        unsafe_allow_html=True,
    )


def onboarding_card() -> None:
    """Shown instead of empty charts until the first translation exists."""
    st.markdown(
        """
        <div class="lg-onboard">
          <h3>Your dashboard is waiting for its first translation ✨</h3>
          <div class="lead">Charts and statistics here are built only from your real usage - nothing is pre-filled.</div>
          <div class="lg-steps">
            <div class="lg-step"><div class="n">1</div><div class="t">Translate something</div>
              <div class="d">Open the Translator, pick two languages and press Translate.</div></div>
            <div class="lg-step"><div class="n">2</div><div class="t">Listen &amp; save</div>
              <div class="d">Hear the result read aloud or star it to keep it in Favorites.</div></div>
            <div class="lg-step"><div class="n">3</div><div class="t">Watch insights grow</div>
              <div class="d">Activity, language and weekday charts appear right here.</div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
