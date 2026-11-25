import pandas as pd
import pytest

from tcmmm.aggregate import (
    all_versions,
    apportion_to_calendar_months,
    distortion_summary,
    naive_media_period,
    naive_week_start,
)
from tcmmm.calendars import (
    days_in_media_period_vs_month,
    label_media_period,
    media_calendar,
    media_year_start,
    weeks_straddling_month_end,
)
from tcmmm.generator import generate, load_scenarios


# ----------------------------------------------------------------- media calendar
@pytest.mark.parametrize("year,weeks", [(2023, 53), (2024, 52), (2025, 52)])
def test_media_year_length(year, weeks):
    assert len(media_calendar(year)) == weeks


def test_media_year_starts_on_monday_of_week_containing_jan1():
    for y in range(2020, 2031):
        s = media_year_start(y)
        assert s.weekday() == 0
        assert 0 <= (pd.Timestamp(y, 1, 1) - pd.Timestamp(s)).days <= 6


def test_445_pattern_and_53rd_week_in_period_12():
    cal = media_calendar(2024)
    assert cal.groupby("media_period").size().tolist() == [4, 4, 5] * 4
    cal53 = media_calendar(2023)
    assert cal53.groupby("media_period").size().loc[12] == 6


def test_five_week_periods_are_longer_than_their_calendar_month():
    t = days_in_media_period_vs_month(2024)
    assert (t.loc[t.media_weeks == 5, "ratio"] > 1.1).all()
    assert (t.loc[t.media_weeks == 4, "ratio"] < 1.0).all()


def test_label_rejects_non_monday():
    with pytest.raises(ValueError):
        label_media_period(pd.Series(pd.to_datetime(["2024-01-02"])))


def test_straddling_weeks_counted():
    weeks = pd.Series(pd.to_datetime(["2024-01-29", "2024-01-22"]))  # first crosses Jan->Feb
    assert weeks_straddling_month_end(weeks) == 1


# ----------------------------------------------------------------- aggregation
def _toy_weekly():
    # one week straddling 2024-01-29 .. 2024-02-04: 3 days in Jan, 4 in Feb
    return pd.DataFrame({"week_start": pd.to_datetime(["2024-01-29"]), "tv_spend": [700.0]}).assign(
        **label_media_period(pd.Series(pd.to_datetime(["2024-01-29"])))[["media_year", "media_period"]]
    )


def test_apportioning_splits_by_days():
    out, rep = apportion_to_calendar_months(_toy_weekly(), "2024-01-01", "2024-02-29")
    assert out.set_index("month").loc["2024-01-01", "tv_spend"] == pytest.approx(300.0)
    assert out.set_index("month").loc["2024-02-01", "tv_spend"] == pytest.approx(400.0)
    assert rep["conservation_gap"] == pytest.approx(0.0, abs=1e-6)


def test_naive_week_start_puts_whole_week_in_january():
    out = naive_week_start(_toy_weekly(), "2024-01-01", "2024-02-29").set_index("month")
    assert out.loc["2024-01-01", "tv_spend"] == 700.0
    assert out.loc["2024-02-01", "tv_spend"] == 0.0


def test_naive_media_period_uses_period_number_as_month():
    # 2024-01-29 is week 5 of media 2024 -> period 2 -> labelled February
    out = naive_media_period(_toy_weekly(), "2024-01-01", "2024-02-29").set_index("month")
    assert out.loc["2024-02-01", "tv_spend"] == 700.0


def test_clipping_reported_not_lost():
    weekly = pd.DataFrame({"week_start": pd.to_datetime(["2023-12-25"]), "tv_spend": [700.0]})
    out, rep = apportion_to_calendar_months(weekly, "2024-01-01", "2024-01-31")
    assert rep["monthly_total"] == pytest.approx(0.0)
    assert rep["clipped_outside_window"] == pytest.approx(700.0)
    assert rep["conservation_gap"] == pytest.approx(0.0, abs=1e-6)


# ----------------------------------------------------------------- generator + error
@pytest.fixture(scope="module")
def main_world():
    cfg = load_scenarios("config/scenarios.yaml")["main"]
    return cfg, generate(cfg)


def test_generator_is_deterministic(main_world):
    cfg, r = main_world
    r2 = generate(cfg)
    pd.testing.assert_frame_equal(r["sales_monthly"], r2["sales_monthly"])


def test_vendor_files_have_expected_grain(main_world):
    _, r = main_world
    assert (pd.to_datetime(r["tv_weekly"]["week_start"]).dt.weekday == 0).all()
    assert (pd.to_datetime(r["sales_monthly"]["month"]).dt.day == 1).all()
    assert len(r["sales_monthly"]) == 36


def test_truth_avg_roi_matches_config(main_world):
    cfg, r = main_world
    for ch in ("tv", "digital", "email"):
        assert r["truth_summary"]["avg_roi"][ch] == pytest.approx(cfg[ch]["avg_roi"], rel=1e-6)


def test_corrected_is_far_closer_to_truth_than_naive(main_world):
    cfg, r = main_world
    versions, rep = all_versions(r["tv_weekly"], r["truth_daily"], cfg["start"], cfg["end"])
    s = distortion_summary(versions).set_index("version")
    assert abs(rep["conservation_gap"]) < 1e-3
    assert s.loc["corrected", "mean_abs_err_pct_of_avg_month"] < 5
    assert s.loc["naive_445", "mean_abs_err_pct_of_avg_month"] > 3 * s.loc["corrected", "mean_abs_err_pct_of_avg_month"]
    assert s.loc["naive_weekstart", "mean_abs_err_pct_of_avg_month"] > 3 * s.loc["corrected", "mean_abs_err_pct_of_avg_month"]
