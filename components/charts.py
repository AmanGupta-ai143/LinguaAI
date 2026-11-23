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
GRID = "rgba(127,127,127,0.18)"

# Hide Plotly's floating toolbar - it overlaps legends and looks cluttered.
PLOT_CONFIG = {"displayModeBar": False, "displaylogo": False}


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


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _bar_marker(color: str):
    """Bar marker with rounded corners (needs plotly >= 5.24; falls back silently)."""
    try:
        go.bar.Marker(cornerradius=6)          # raises ValueError on older plotly versions
        return dict(color=color, cornerradius=6)
    except (ValueError, TypeError, AttributeError):
        return dict(color=color)


def _labels(values) -> list[str]:
    """Value labels for bars - blank for zero so empty categories stay clean."""
    return [str(int(v)) if v else "" for v in values]


def _count_axis(fig: go.Figure, max_value: float, axis: str = "y") -> None:
    """Whole-number ticks with headroom so labels above the bars are never clipped."""
    top = max_value + (1 if max_value < 5 else max_value * 0.18)
    update = fig.update_yaxes if axis == "y" else fig.update_xaxes
    update(range=[0, top], tickformat="d", dtick=1 if max_value <= 5 else None)


def _gap(n_categories: int) -> float:
    """Few categories -> larger gap so bars never become giant blocks."""
    return 0.35 if n_categories >= 6 else (0.5 if n_categories >= 3 else 0.62)


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
            line=dict(color=color, width=3), fill="tozeroy", fillcolor=_rgba(color, 0.12),
            marker=dict(size=9, color=color),
            hovertemplate="%{x|" + fmt + "}<br><b>%{y}</b> translations<extra></extra>",
        )
    )
    _layout(fig, f"Translation activity - {period.lower()}", "Date", "Translations")
    _count_axis(fig, float(data["translations"].max()))
    fig.update_layout(showlegend=False)
    return fig


def most_used_chart(counts: pd.DataFrame, top_n: int = 8) -> Optional[go.Figure]:
    """Chart 2 - horizontal bars of the most frequently chosen target languages."""
    if counts.empty:
        return None
    data = counts.head(top_n).iloc[::-1]  # biggest bar on top
    fig = go.Figure(
        go.Bar(
            x=data["translations"], y=data["language"], orientation="h", name="Translations",
            marker=_bar_marker(palette()[0]), text=_labels(data["translations"]), textposition="outside",
            width=0.5, cliponaxis=False, hovertemplate="%{y}<br><b>%{x}</b> translations<extra></extra>",
        )
    )
    _layout(fig, "Most used target languages", "Translations", "Target language",
            height=max(260, 110 + 44 * len(data)))
    _count_axis(fig, float(data["translations"].max()), axis="x")
    fig.update_layout(showlegend=False, bargap=_gap(len(data)))
    return fig


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
            labels=dist["language"], values=dist["translations"], hole=0.58, sort=False,
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
            x=part["language"].astype(str), y=part["translations"], name=role, marker=_bar_marker(color),
            text=_labels(part["translations"]), textposition="outside", cliponaxis=False,
            hovertemplate="%{x} as " + role.lower() + "<br><b>%{y}</b> translations<extra></extra>",
        )
    _layout(fig, "Source vs target languages", "Language", "Translations")
    _count_axis(fig, float(data["translations"].max()))
    fig.update_layout(barmode="group", bargap=_gap(len(keep)), bargroupgap=0.08)
    return fig


def weekday_chart(data: pd.DataFrame) -> Optional[go.Figure]:
    """Chart 6 - translations per weekday."""
    if data.empty or data["translations"].sum() == 0:
        return None
    fig = go.Figure(
        go.Bar(
            x=data["weekday"].str[:3], y=data["translations"], name="Translations",
            marker=_bar_marker(palette()[2]), text=_labels(data["translations"]), textposition="outside",
            width=0.55, cliponaxis=False, customdata=data["weekday"],
            hovertemplate="%{customdata}<br><b>%{y}</b> translations<extra></extra>",
        )
    )
    _layout(fig, "Usage by weekday", "Weekday", "Translations")
    _count_axis(fig, float(data["translations"].max()))
    fig.update_layout(showlegend=False, bargap=0.35)
    return fig
