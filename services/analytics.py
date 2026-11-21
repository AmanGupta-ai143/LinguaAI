"""Pure-pandas aggregations behind the dashboard charts.

Every function takes the history DataFrame (see ``DatabaseManager.get_history_df``)
and returns a small DataFrame - no randomness, no placeholder data.
"""
from __future__ import annotations

import pandas as pd

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
FREQUENCIES = {"Daily": "D", "Weekly": "W-SUN", "Monthly": "MS"}


def activity_over_time(df: pd.DataFrame, period: str = "Daily") -> pd.DataFrame:
    """Translations per day / week (starting Monday) / month. Columns: period, translations."""
    if df.empty:
        return pd.DataFrame(columns=["period", "translations"])
    indexed = df.set_index("timestamp")
    if period == "Weekly":
        # weeks run Monday-Sunday; label each bucket with the Monday that starts it
        series = indexed.resample("W-SUN", label="left", closed="right").size()
        series.index = series.index + pd.Timedelta(days=1)
    else:
        series = indexed.resample(FREQUENCIES[period]).size()
    out = series.rename("translations").reset_index()
    out.columns = ["period", "translations"]
    return out


def language_counts(df: pd.DataFrame, column: str = "target_language") -> pd.DataFrame:
    """Rows per language, most frequent first. Columns: language, translations."""
    if df.empty:
        return pd.DataFrame(columns=["language", "translations"])
    out = df[column].value_counts().rename_axis("language").reset_index(name="translations")
    return out.sort_values(["translations", "language"], ascending=[False, True]).reset_index(drop=True)


def distribution(df: pd.DataFrame, top_n: int = 6, column: str = "target_language") -> pd.DataFrame:
    """Share of translations per language, grouping the tail into 'Other'.

    Columns: language, translations, percent.
    """
    counts = language_counts(df, column)
    if counts.empty:
        return pd.DataFrame(columns=["language", "translations", "percent"])
    if len(counts) > top_n:
        head, tail = counts.iloc[:top_n], counts.iloc[top_n:]
        counts = pd.concat(
            [head, pd.DataFrame([{"language": "Other", "translations": int(tail["translations"].sum())}])],
            ignore_index=True,
        )
    counts["percent"] = counts["translations"] / counts["translations"].sum() * 100
    return counts


def source_vs_target(df: pd.DataFrame) -> pd.DataFrame:
    """Per language: how often it was used as source and as target.

    Columns: language, role ("Source"/"Target"), translations.
    """
    if df.empty:
        return pd.DataFrame(columns=["language", "role", "translations"])
    src = df["source_language"].value_counts().rename_axis("language").reset_index(name="translations")
    src["role"] = "Source"
    tgt = df["target_language"].value_counts().rename_axis("language").reset_index(name="translations")
    tgt["role"] = "Target"
    out = pd.concat([src, tgt], ignore_index=True)
    order = out.groupby("language")["translations"].sum().sort_values(ascending=False).index.tolist()
    out["language"] = pd.Categorical(out["language"], categories=order, ordered=True)
    return out.sort_values(["language", "role"]).reset_index(drop=True)


def weekday_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Translations per weekday (Monday-Sunday, zeros included). Columns: weekday, translations."""
    counts = (
        df["timestamp"].dt.day_name().value_counts() if not df.empty else pd.Series(dtype="int64")
    )
    out = pd.DataFrame({"weekday": WEEKDAYS})
    out["translations"] = out["weekday"].map(counts).fillna(0).astype(int)
    return out
