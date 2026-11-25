"""Calendar utilities: the media (broadcast) calendar vs the calendar month.

The case defines the broadcast / media calendar as Monday-to-Sunday weeks grouped
into 4-4-5 quarters. That calendar does not line up with calendar months, which is
the root cause of the error we are investigating.

Conventions used throughout this project (see docs/assumptions.md, A-01 and A-02):
  * A media week is identified by its Monday (``week_start``).
  * A media year starts on the Monday of the week that contains 1 January.
    It therefore has 52 or 53 weeks.
  * Periods (media "months") follow a 4-4-5 pattern per quarter. In a 53-week
    year the extra week is appended to period 12.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

PATTERN_445 = [4, 4, 5] * 4  # weeks per media period, 12 periods = 52 weeks


def monday_on_or_before(d: date) -> date:
    d = pd.Timestamp(d).date()
    return d - timedelta(days=d.weekday())


def media_year_start(year: int) -> date:
    """Monday of the week containing 1 January of ``year``."""
    return monday_on_or_before(date(year, 1, 1))


def media_calendar(year: int) -> pd.DataFrame:
    """One row per media week of ``year``: week_start, media_year, media_period, week_in_year."""
    start = media_year_start(year)
    end_excl = media_year_start(year + 1)
    n_weeks = (end_excl - start).days // 7
    if n_weeks not in (52, 53):  # pragma: no cover - defensive
        raise ValueError(f"unexpected media year length {n_weeks} weeks for {year}")
    periods = []
    for p, n in enumerate(PATTERN_445, start=1):
        periods += [p] * n
    if n_weeks == 53:
        periods.append(12)  # extra week goes to the last period
    weeks = [start + timedelta(weeks=i) for i in range(n_weeks)]
    return pd.DataFrame(
        {
            "week_start": pd.to_datetime(weeks),
            "media_year": year,
            "media_period": periods,
            "week_in_year": range(1, n_weeks + 1),
        }
    )


def media_calendar_range(first_year: int, last_year: int) -> pd.DataFrame:
    return pd.concat([media_calendar(y) for y in range(first_year, last_year + 1)], ignore_index=True)


def label_media_period(week_start: pd.Series) -> pd.DataFrame:
    """Attach media_year and media_period to a series of Monday week starts."""
    ws = pd.to_datetime(week_start)
    if (ws.dt.weekday != 0).any():
        raise ValueError("week_start values must all be Mondays")
    years = range(ws.dt.year.min() - 1, ws.dt.year.max() + 2)
    cal = media_calendar_range(years.start, years.stop - 1)
    out = pd.DataFrame({"week_start": ws}).merge(cal, on="week_start", how="left")
    if out["media_period"].isna().any():  # pragma: no cover - defensive
        raise ValueError("some weeks could not be mapped to the media calendar")
    return out


def weeks_straddling_month_end(week_start: pd.Series) -> int:
    """How many Mon-Sun weeks cross a calendar-month boundary."""
    ws = pd.to_datetime(week_start)
    we = ws + pd.Timedelta(days=6)
    return int((ws.dt.month != we.dt.month).sum())


def month_starts(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(start, end, freq="MS")


def days_in_media_period_vs_month(year: int) -> pd.DataFrame:
    """Diagnostic table: days in each media period vs days in the matching calendar month."""
    cal = media_calendar(year)
    per = cal.groupby("media_period").size().rename("media_weeks").to_frame()
    per["media_days"] = per["media_weeks"] * 7
    per["calendar_days"] = [pd.Period(f"{year}-{m:02d}").days_in_month for m in per.index]
    per["ratio"] = per["media_days"] / per["calendar_days"]
    return per.reset_index()


__all__ = [
    "PATTERN_445",
    "media_year_start",
    "media_calendar",
    "media_calendar_range",
    "label_media_period",
    "weeks_straddling_month_end",
    "month_starts",
    "days_in_media_period_vs_month",
    "monday_on_or_before",
]
