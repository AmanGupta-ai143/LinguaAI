"""Plotly charts for the dashboard.

Every function receives an already-aggregated DataFrame from ``services.analytics``
(i.e. real data from the history table) and returns a Plotly figure, or ``None``
when there is nothing to plot - the page then shows an empty state instead.

Colours: the categorical palettes below were checked with a colour-blind-safety
validator (adjacent-pair CVD separation, lightness band, chroma floor) for both
the light and the dark surface. Value labels are always visible because some light
mode hues have lower contrast against the background.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PALETTES = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"],
    "dark": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"],
}
OTHER_COLOR = "#898781"   # neutral grey for the folded "Other" slice
GRID = "rgba(127,127,127,0.22)"


def _theme_type() -> str:
    """'dark' or 'light' - uses the active Streamlit theme when it can be read."""
    try:
        theme = getattr(st.context, "theme", None)
        if theme is not None and getattr(theme, "type", None) in ("light", "dark"):
            return theme.type
    except Exception:
        pass
    return "light"


def palette() -> list[str]:
    return PALETTES[_theme_type()]


def _layout(fig: go.Figure, title: str, x_title: Optional[str], y_title: Optional[str], height: int = 340) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=16)),
        height=height,
        margin=dict(l=10, r=10, t=55, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        bargap=0.35,
        hoverlabel=dict(font_size=13),
    )
    fig.update_xaxes(title=x_title, gridcolor=GRID, zeroline=False, showline=False, automargin=True)
    fig.update_yaxes(title=y_title, gridcolor=GRID, zeroline=False, showline=False, automargin=True)
    return fig


def activity_chart(data: pd.DataFrame, period: str) -> Optional[go.Figure]:
    """Chart 1 - line chart of translations per day / week / month."""
    if data.empty:
        return None
    color = palette()[0]
    fmt = {"Daily": "%d %b %Y", "Weekly": "Week of %d %b %Y", "Monthly": "%B %Y"}[period]
    fig = go.Figure(
        go.Scatter(
            x=data["period"], y=data["translations"], mode="lines+markers", name="Translations",
            line=dict(color=color, width=2.5, shape="linear"),
            marker=dict(size=8, color=color, line=dict(width=2, color="rgba(127,127,127,0.0)")),
            hovertemplate="%{x|" + fmt + "}<br><b>%{y}</b> translations<extra></extra>",
        )
    )
    _layout(fig, f"Translation activity - {period.lower()}", "Date", "Translations")
    fig.update_yaxes(rangemode="tozero", dtick=1 if data["translations"].max() <= 8 else None)
    fig.update_layout(showlegend=False)
    return fig


def _bar_h(data: pd.DataFrame, title: str, x_title: str, y_title: str, color: str) -> go.Figure:
    data = data.iloc[::-1]  # biggest bar on top
    fig = go.Figure(
        go.Bar(
            x=data["translations"], y=data["language"], orientation="h", name="Translations",
            marker=dict(color=color), text=data["translations"], textposition="outside",
            cliponaxis=False, hovertemplate="%{y}<br><b>%{x}</b> translations<extra></extra>",
        )
    )
    _layout(fig, title, x_title, y_title, height=max(300, 60 + 38 * len(data)))
    fig.update_xaxes(rangemode="tozero")
    fig.update_layout(showlegend=False)
    return fig


def most_used_chart(counts: pd.DataFrame, top_n: int = 8) -> Optional[go.Figure]:
    """Chart 2 - horizontal bars of the most frequently chosen target languages."""
    if counts.empty:
        return None
    return _bar_h(counts.head(top_n), "Most used target languages", "Translations", "Target language", palette()[0])


def distribution_chart(dist: pd.DataFrame) -> Optional[go.Figure]:
    """Chart 3 - donut of the share of translations per target language."""
    if dist.empty:
        return None
    colors = palette()
    slice_colors, i = [], 0
    for name in dist["language"]:
        if name == "Other":
            slice_colors.append(OTHER_COLOR)
        else:
            slice_colors.append(colors[i % len(colors)])
            i += 1
    fig = go.Figure(
        go.Pie(
            labels=dist["language"], values=dist["translations"], hole=0.55, sort=False,
            marker=dict(colors=slice_colors, line=dict(color="rgba(127,127,127,0.0)", width=2)),
            textinfo="percent", textposition="inside", insidetextorientation="horizontal",
            hovertemplate="%{label}<br><b>%{value}</b> translations (%{percent})<extra></extra>",
        )
    )
    _layout(fig, "Language distribution (target)", None, None, height=360)
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5))
    return fig


def source_target_chart(data: pd.DataFrame, top_n: int = 8) -> Optional[go.Figure]:
    """Chart 5 - grouped bars comparing how often a language is source vs target."""
    if data.empty:
        return None
    keep = list(data["language"].cat.categories[:top_n])
    data = data[data["language"].isin(keep)]
    colors = palette()
    fig = go.Figure()
    for role, color in (("Source", colors[0]), ("Target", colors[1])):
        part = data[data["role"] == role]
        fig.add_bar(
            x=part["language"].astype(str), y=part["translations"], name=role, marker=dict(color=color),
            text=part["translations"], textposition="outside", cliponaxis=False,
            hovertemplate="%{x} as " + role.lower() + "<br><b>%{y}</b> translations<extra></extra>",
        )
    _layout(fig, "Source vs target languages", "Language", "Translations")
    fig.update_layout(barmode="group")
    fig.update_yaxes(rangemode="tozero")
    return fig


def weekday_chart(data: pd.DataFrame) -> Optional[go.Figure]:
    """Chart 6 - translations per weekday."""
    if data.empty or data["translations"].sum() == 0:
        return None
    fig = go.Figure(
        go.Bar(
            x=data["weekday"], y=data["translations"], name="Translations", marker=dict(color=palette()[2]),
            text=data["translations"], textposition="outside", cliponaxis=False,
            hovertemplate="%{x}<br><b>%{y}</b> translations<extra></extra>",
        )
    )
    _layout(fig, "Usage by weekday", "Weekday", "Translations")
    fig.update_yaxes(rangemode="tozero")
    fig.update_layout(showlegend=False)
    return fig
