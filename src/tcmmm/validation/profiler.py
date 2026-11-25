"""Deterministic data profiler: infers grain and calendar facts from the file itself.

It can tell: grain (from spacing), which weekday dates fall on, whether monthly dates are
first-of-month, gaps, duplicates, period-label columns, and weeks that cross month ends.
It CANNOT tell: whether a date marks the start or the end of a period, or whether a
first-of-month date really means a calendar month (vs a fiscal or broadcast month).
That gap is exactly what the LLM spec reader is for, and why its claims are cross-checked here.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATE_CANDIDATES = ("week_start", "week_ending", "week_end", "month", "date", "period_start")
PERIOD_COLUMNS = ("media_period", "media_year", "fiscal_period", "broadcast_month", "period")
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def find_date_column(df: pd.DataFrame) -> str:
    for c in DATE_CANDIDATES:
        if c in df.columns:
            return c
    for c in df.columns:
        try:
            pd.to_datetime(df[c], format="%Y-%m-%d")
            return c
        except (ValueError, TypeError):
            continue
    raise ValueError("no date column found")


def infer_grain(dates: pd.Series) -> tuple[str, dict]:
    d = pd.to_datetime(dates).sort_values().diff().dt.days.dropna()
    if d.empty:
        return "unknown", {}
    counts = d.value_counts().to_dict()
    share_7 = (d == 7).mean()
    share_1 = (d == 1).mean()
    share_m = d.between(28, 31).mean()
    if share_1 > 0.95:
        g = "daily"
    elif share_7 > 0.95:
        g = "weekly"
    elif share_m > 0.95:
        g = "monthly"
    elif share_7 + share_m > 0.95 and share_7 > 0.05 and share_m > 0.05:
        g = "mixed"
    else:
        g = "unknown"
    return g, {"spacing_days_counts": {int(k): int(v) for k, v in counts.items()}}


def profile(path: str | Path) -> dict:
    df = pd.read_csv(path)
    col = find_date_column(df)
    dates = pd.to_datetime(df[col])
    grain, extra = infer_grain(dates)
    wd = dates.dt.weekday.value_counts()
    dominant_wd = WEEKDAYS[int(wd.idxmax())] if len(wd) else None
    prof = {
        "file": str(path),
        "date_column": col,
        "rows": int(len(df)),
        "first": str(dates.min().date()),
        "last": str(dates.max().date()),
        "grain": grain,
        "dominant_weekday": dominant_wd,
        "weekday_purity": float(wd.max() / wd.sum()) if len(wd) else 0.0,
        "all_first_of_month": bool((dates.dt.day == 1).all()),
        "duplicates": int(dates.duplicated().sum()),
        "period_columns": [c for c in PERIOD_COLUMNS if c in df.columns],
        **extra,
    }
    if grain == "weekly":
        ends = dates + pd.Timedelta(days=6)
        prof["weeks_crossing_month_end"] = int((dates.dt.month != ends.dt.month).sum())
        expected = pd.date_range(dates.min(), dates.max(), freq="7D")
        prof["missing_periods"] = int(len(expected.difference(dates)))
    elif grain == "monthly":
        expected = pd.date_range(dates.min(), dates.max(), freq="MS")
        prof["missing_periods"] = int(len(expected.difference(dates))) if prof["all_first_of_month"] else None
    return prof
