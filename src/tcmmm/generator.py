"""Synthetic data generator with a KNOWN true effect per channel.

The world is simulated at DAILY grain, then written out the way the vendors deliver it:
  * TV:            weekly, Monday-Sunday media-buying weeks, labelled with the 4-4-5 media period
  * Digital/email: calendar month
  * Sales:         calendar month

The daily truth (spend and contribution per channel) is written separately and is used
ONLY for scoring. The modelling code never reads it.

True response per channel c on day t:
    adstock_t = spend_t + alpha_c * adstock_{t-1}          alpha_c = 0.5 ** (1 / half_life_days)
    contrib_t = beta_c * (1 - exp(-adstock_t / k_c))       k_c = mean(adstock) / saturation_c
beta_c is calibrated so that total contribution / total spend = avg_roi_c over the window.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .calendars import label_media_period, monday_on_or_before

CHANNELS = ["tv", "digital", "email"]


# --------------------------------------------------------------------------- config
def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_scenarios(path: str | Path = "config/scenarios.yaml") -> dict[str, dict]:
    raw = yaml.safe_load(Path(path).read_text())
    return {name: deep_merge(raw["defaults"], ov or {}) for name, ov in raw["scenarios"].items()}


# --------------------------------------------------------------------------- response
def adstock_daily(x: np.ndarray, half_life_days: float) -> np.ndarray:
    alpha = 0.5 ** (1.0 / half_life_days)
    out = np.empty_like(x, dtype=float)
    acc = 0.0
    for i, v in enumerate(x):
        acc = v + alpha * acc
        out[i] = acc
    return out


@dataclass
class ChannelTruth:
    half_life_days: float
    k: float
    beta: float

    def contribution(self, spend: np.ndarray) -> np.ndarray:
        a = adstock_daily(spend, self.half_life_days)
        return self.beta * (1.0 - np.exp(-a / self.k))


# --------------------------------------------------------------------------- spend paths
def _tv_weekly(cfg: dict, week_starts: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    tv = cfg["tv"]
    n = len(week_starts)
    level = tv["weekly_mean"] * np.exp(rng.normal(-0.5 * tv["weekly_sd_log"] ** 2, tv["weekly_sd_log"], n))
    if tv["flighting"] == "always_on":
        return level
    on = np.zeros(n, dtype=bool)
    i = int(rng.integers(0, 3))
    while i < n:
        f = int(rng.integers(tv["flight_weeks"][0], tv["flight_weeks"][1] + 1))
        g = int(rng.integers(tv["gap_weeks"][0], tv["gap_weeks"][1] + 1))
        on[i : i + f] = True
        i += f + g
    return np.where(on, level, 0.0)  # weekly_mean is the in-flight weekly level


def _daily_delivery_weights(days: pd.DatetimeIndex, cfg: dict, rng: np.random.Generator) -> np.ndarray:
    w = np.where(days.weekday >= 5, cfg["weekend_delivery_weight"], 1.0)
    return w * np.exp(rng.normal(0, cfg["delivery_noise_sd"], len(days)))


def _monthly_correlated(cfg_c: dict, tv_month_z: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    rho = cfg_c["corr_with_tv"]
    e = rng.normal(0, 1, len(tv_month_z))
    z = rho * tv_month_z + np.sqrt(1 - rho**2) * e
    sd = cfg_c["monthly_sd_log"]
    return cfg_c["monthly_mean"] * np.exp(sd * z - 0.5 * sd**2)


# --------------------------------------------------------------------------- main entry
def generate(cfg: dict) -> dict:
    rng = np.random.default_rng(cfg["seed"])
    start, end = pd.Timestamp(cfg["start"]), pd.Timestamp(cfg["end"])
    sim_start = monday_on_or_before((start - pd.Timedelta(days=cfg["burn_in_days"])).date())
    last_week = monday_on_or_before(end.date())
    week_starts = pd.date_range(sim_start, last_week, freq="7D")
    days = pd.date_range(week_starts[0], week_starts[-1] + pd.Timedelta(days=6), freq="D")

    # ---- TV: weekly buy, delivered across the 7 days with weekend-heavy, noisy weights
    tv_week = _tv_weekly(cfg, week_starts, rng)
    w = _daily_delivery_weights(days, cfg, rng).reshape(-1, 7)
    w = w / w.sum(axis=1, keepdims=True)
    tv_daily = (w * tv_week[:, None]).ravel()

    # ---- Digital / email: monthly calendar budgets, spread evenly over days of the month
    months = pd.period_range(days[0], days[-1], freq="M")
    tv_m = pd.Series(tv_daily, index=days).groupby(days.to_period("M")).sum().reindex(months).values
    tv_z = (tv_m - tv_m.mean()) / (tv_m.std() + 1e-9)
    daily = pd.DataFrame(index=days)
    daily["tv"] = tv_daily
    for ch in ("digital", "email"):
        m_spend = pd.Series(_monthly_correlated(cfg[ch], tv_z, rng), index=months)
        per_day = m_spend / m_spend.index.days_in_month
        daily[ch] = per_day.reindex(days.to_period("M")).values

    # ---- calibrate true response so avg ROI over the window matches config
    in_win = (days >= start) & (days <= end)
    truths: dict[str, ChannelTruth] = {}
    for ch in CHANNELS:
        c = cfg[ch]
        a = adstock_daily(daily[ch].values, c["half_life_days"])
        k = a[in_win].mean() / c["saturation"]
        shape = 1.0 - np.exp(-a / k)
        beta = c["avg_roi"] * daily.loc[in_win, ch].sum() / shape[in_win].sum()
        truths[ch] = ChannelTruth(c["half_life_days"], k, beta)
        daily[f"contrib_{ch}"] = truths[ch].contribution(daily[ch].values)

    # ---- baseline: trend + yearly seasonality + January insurance-reset dip
    t_years = (days - start).days / 365.25
    doy = days.dayofyear.values
    base = cfg["base_daily_sales"] * (1 + cfg["trend_per_year"] * t_years)
    base = base * (1 + cfg["seasonality_amp"] * np.sin(2 * np.pi * (doy - 80) / 365.25))
    base = base * np.where(days.month == 1, 1 - cfg["january_dip"], 1.0)
    daily["baseline"] = base

    # ---- monthly sales (calendar months, window only) with multiplicative noise
    win = daily.loc[in_win]
    mon = win.groupby(win.index.to_period("M")).sum()
    noise = np.exp(rng.normal(-0.5 * cfg["sales_noise_sd"] ** 2, cfg["sales_noise_sd"], len(mon)))
    mon["sales"] = (mon["baseline"] + mon[[f"contrib_{c}" for c in CHANNELS]].sum(axis=1)) * noise
    mon.index = mon.index.to_timestamp()

    # ---- vendor files
    tv_vendor = label_media_period(pd.Series(week_starts))
    tv_vendor["tv_spend"] = np.round(tv_week, 2)
    in_scope = (tv_vendor["week_start"] + pd.Timedelta(days=6) >= start) & (tv_vendor["week_start"] <= end)
    tv_vendor = tv_vendor.loc[in_scope].reset_index(drop=True)
    digital = pd.DataFrame({"month": mon.index, "digital_spend": mon["digital"].round(2).values})
    email = pd.DataFrame({"month": mon.index, "email_spend": mon["email"].round(2).values})
    sales = pd.DataFrame({"month": mon.index, "net_revenue": mon["sales"].round(2).values})

    truth_summary = _truth_summary(cfg, daily, in_win, truths)
    return {
        "tv_weekly": tv_vendor,
        "digital_monthly": digital,
        "email_monthly": email,
        "sales_monthly": sales,
        "truth_daily": daily.reset_index(names="date"),
        "truth_monthly": mon.reset_index(names="month"),
        "truth_summary": truth_summary,
        "truths": truths,
    }


# --------------------------------------------------------------------------- ground truth
def _window_contrib(truths, daily, in_win, spend_override=None) -> dict[str, float]:
    out = {}
    for ch in CHANNELS:
        s = daily[ch].values if spend_override is None else spend_override[ch]
        out[ch] = float(truths[ch].contribution(s)[in_win].sum())
    return out


def reallocate(spend: dict[str, np.ndarray], in_win: np.ndarray, tv_cut_share: float) -> dict[str, np.ndarray]:
    """Cut TV by tv_cut_share inside the window; give the money to digital and email pro rata."""
    new = {k: v.copy() for k, v in spend.items()}
    moved = tv_cut_share * spend["tv"][in_win].sum()
    new["tv"][in_win] *= 1 - tv_cut_share
    recip = {c: spend[c][in_win].sum() for c in ("digital", "email")}
    tot = sum(recip.values())
    for c, s in recip.items():
        new[c][in_win] *= 1 + moved * (s / tot) / s
    return new


def _truth_summary(cfg, daily, in_win, truths) -> dict:
    spend = {c: daily[c].values for c in CHANNELS}
    base = _window_contrib(truths, daily, in_win)
    total_sales = float(daily.loc[in_win, "baseline"].sum() + sum(base.values()))
    tot_spend = {c: float(spend[c][in_win].sum()) for c in CHANNELS}
    mroi = {}
    for c in CHANNELS:
        bumped = {k: v.copy() for k, v in spend.items()}
        bumped[c][in_win] *= 1.01
        mroi[c] = (_window_contrib(truths, daily, in_win, bumped)[c] - base[c]) / (0.01 * tot_spend[c])
    shifted = reallocate(spend, in_win, cfg["reallocation"]["tv_cut_share"])
    after = _window_contrib(truths, daily, in_win, shifted)
    delta = sum(after.values()) - sum(base.values())
    return {
        "window": [cfg["start"], cfg["end"]],
        "total_sales": total_sales,
        "spend": tot_spend,
        "contribution": base,
        "contribution_share": {c: base[c] / total_sales for c in CHANNELS},
        "avg_roi": {c: base[c] / tot_spend[c] for c in CHANNELS},
        "marginal_roi": mroi,
        "shift_delta_sales": delta,
        "shift_delta_pct_of_sales": delta / total_sales,
        "shift_moved_budget": cfg["reallocation"]["tv_cut_share"] * tot_spend["tv"],
    }


def write_scenario(name: str, cfg: dict, out_root: str | Path = "data") -> Path:
    res = generate(cfg)
    out = Path(out_root) / name
    (out / "vendor").mkdir(parents=True, exist_ok=True)
    (out / "_truth").mkdir(parents=True, exist_ok=True)
    res["tv_weekly"].to_csv(out / "vendor" / "tv_media_weekly.csv", index=False)
    res["digital_monthly"].to_csv(out / "vendor" / "digital_monthly.csv", index=False)
    res["email_monthly"].to_csv(out / "vendor" / "email_monthly.csv", index=False)
    res["sales_monthly"].to_csv(out / "vendor" / "sales_monthly.csv", index=False)
    res["truth_daily"].to_csv(out / "_truth" / "truth_daily.csv", index=False)
    (out / "_truth" / "truth_summary.json").write_text(json.dumps(res["truth_summary"], indent=2))
    (out / "_truth" / "config_used.json").write_text(json.dumps(cfg, indent=2))
    return out
