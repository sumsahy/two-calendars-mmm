"""Weekly media-calendar TV spend -> calendar months: two naive ways and the correct way.

All functions return a DataFrame with columns ``month`` (first day of calendar month) and
``tv_spend``, restricted to the analysis window months.
"""
from __future__ import annotations

import pandas as pd


def _window_months(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(pd.Timestamp(start).to_period("M").to_timestamp(), end, freq="MS")


def naive_media_period(tv_weekly: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """NAIVE 1: sum weeks by 4-4-5 media period and treat period N of year Y as calendar month N.

    This is what happens when a media-period column is joined to a calendar month key.
    """
    df = tv_weekly.copy()
    df["month"] = pd.to_datetime(
        dict(year=df["media_year"], month=df["media_period"], day=1)
    )
    out = df.groupby("month", as_index=False)["tv_spend"].sum()
    return _restrict(out, start, end)


def naive_week_start(tv_weekly: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """NAIVE 2: give each whole week to the calendar month its Monday falls in."""
    df = tv_weekly.copy()
    df["month"] = pd.to_datetime(df["week_start"]).dt.to_period("M").dt.to_timestamp()
    out = df.groupby("month", as_index=False)["tv_spend"].sum()
    return _restrict(out, start, end)


def explode_to_days(tv_weekly: pd.DataFrame, weights: list[float] | None = None) -> pd.DataFrame:
    """One row per day. Default spreads each week's spend evenly over Monday..Sunday."""
    w = [1 / 7] * 7 if weights is None else [x / sum(weights) for x in weights]
    rows = []
    for ws, spend in zip(pd.to_datetime(tv_weekly["week_start"]), tv_weekly["tv_spend"]):
        for i in range(7):
            rows.append((ws + pd.Timedelta(days=i), spend * w[i]))
    return pd.DataFrame(rows, columns=["date", "tv_spend"])


def apportion_to_calendar_months(
    tv_weekly: pd.DataFrame, start: str, end: str, weights: list[float] | None = None
) -> tuple[pd.DataFrame, dict]:
    """CORRECT: spread each week over its days, clip to the window, sum by calendar month.

    Returns the monthly table and a conservation report (spend in == spend out + clipped).
    """
    days = explode_to_days(tv_weekly, weights)
    in_win = (days["date"] >= pd.Timestamp(start)) & (days["date"] <= pd.Timestamp(end))
    kept = days.loc[in_win].copy()
    kept["month"] = kept["date"].dt.to_period("M").dt.to_timestamp()
    out = kept.groupby("month", as_index=False)["tv_spend"].sum()
    out = _restrict(out, start, end)
    report = {
        "weekly_total": float(tv_weekly["tv_spend"].sum()),
        "monthly_total": float(out["tv_spend"].sum()),
        "clipped_outside_window": float(days.loc[~in_win, "tv_spend"].sum()),
    }
    report["conservation_gap"] = report["weekly_total"] - report["monthly_total"] - report["clipped_outside_window"]
    return out, report


def oracle_from_daily(truth_daily: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """SCORING ONLY: true daily TV delivery summed by calendar month."""
    d = truth_daily[["date", "tv"]].copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d[(d["date"] >= pd.Timestamp(start)) & (d["date"] <= pd.Timestamp(end))]
    d["month"] = d["date"].dt.to_period("M").dt.to_timestamp()
    return _restrict(d.groupby("month", as_index=False)["tv"].sum().rename(columns={"tv": "tv_spend"}), start, end)


def _restrict(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    months = _window_months(start, end)
    return (
        df.set_index("month")
        .reindex(months, fill_value=0.0)
        .rename_axis("month")
        .reset_index()
    )


def all_versions(tv_weekly, truth_daily, start, end) -> tuple[dict[str, pd.DataFrame], dict]:
    corrected, report = apportion_to_calendar_months(tv_weekly, start, end)
    versions = {
        "oracle": oracle_from_daily(truth_daily, start, end),
        "naive_445": naive_media_period(tv_weekly, start, end),
        "naive_weekstart": naive_week_start(tv_weekly, start, end),
        "corrected": corrected,
    }
    return versions, report


def distortion_table(versions: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Monthly TV under each version and the % error vs oracle."""
    base = versions["oracle"].set_index("month")["tv_spend"]
    tbl = pd.DataFrame({k: v.set_index("month")["tv_spend"] for k, v in versions.items()})
    for k in versions:
        if k != "oracle":
            tbl[f"{k}_err_pct"] = 100 * (tbl[k] - base) / base.where(base > 0)
    return tbl


def distortion_summary(versions: dict[str, pd.DataFrame]) -> pd.DataFrame:
    base = versions["oracle"].set_index("month")["tv_spend"]
    rows = []
    for k, v in versions.items():
        s = v.set_index("month")["tv_spend"]
        err = s - base
        rows.append(
            {
                "version": k,
                "mean_abs_err_pct_of_avg_month": 100 * err.abs().mean() / base.mean(),
                "max_abs_err_pct_of_avg_month": 100 * err.abs().max() / base.mean(),
                "corr_with_oracle": float(s.corr(base)),
                "total_vs_oracle_pct": 100 * (s.sum() - base.sum()) / base.sum(),
            }
        )
    return pd.DataFrame(rows)
