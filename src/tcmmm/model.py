"""A small Bayesian MMM in PyMC, written out in full so every line can be explained.

Monthly model, on scaled data (spend / channel mean, sales / mean sales):

    sales_t = intercept + trend * t + fourier_t . gamma + jan_t * jan_effect
              + sum_c beta_c * (1 - exp(-lam_c * adstock_c,t)) + noise

    adstock_c,t = sum_{l=0..L-1} w_c,l * x_c,t-l     w_c,l proportional to alpha_c ** l (normalised)

Counterfactuals (marginal ROI, the 15% shift) are computed in NumPy from posterior draws,
using the SAME transformation as the model (``media_contrib_np``). A unit test checks the
PyMC and NumPy versions agree.
"""
from __future__ import annotations

from dataclasses import dataclass

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt

CHANNELS = ["tv", "digital", "email"]
L_MAX = 3  # current month + 2 months of carryover


# --------------------------------------------------------------------------- design
def lag_matrix(x: np.ndarray, l_max: int = L_MAX) -> np.ndarray:
    """(T, l_max) matrix whose column l is x shifted down by l (zero padded)."""
    T = len(x)
    out = np.zeros((T, l_max))
    for l in range(l_max):
        out[l:, l] = x[: T - l]
    return out


@dataclass
class Design:
    months: pd.DatetimeIndex
    x_raw: np.ndarray        # (T, C) spend in USD
    x_scale: np.ndarray      # (C,) channel means
    y_raw: np.ndarray        # (T,) sales in USD
    y_scale: float
    controls: np.ndarray     # (T, K)
    control_names: list[str]

    @property
    def x(self) -> np.ndarray:
        return self.x_raw / self.x_scale

    @property
    def y(self) -> np.ndarray:
        return self.y_raw / self.y_scale


def build_design(df: pd.DataFrame) -> Design:
    """df columns: month, tv_spend, digital_spend, email_spend, net_revenue."""
    df = df.sort_values("month").reset_index(drop=True)
    months = pd.DatetimeIndex(df["month"])
    x_raw = df[[f"{c}_spend" for c in CHANNELS]].to_numpy(float)
    y_raw = df["net_revenue"].to_numpy(float)
    t = np.arange(len(df)) / 12.0
    m = months.month.values
    controls = np.column_stack(
        [
            t,
            np.sin(2 * np.pi * m / 12),
            np.cos(2 * np.pi * m / 12),
            (m == 1).astype(float),
        ]
    )
    return Design(months, x_raw, x_raw.mean(axis=0), y_raw, float(y_raw.mean()), controls,
                  ["trend", "sin1", "cos1", "january"])


# --------------------------------------------------------------------------- model
def build_model(d: Design) -> pm.Model:
    coords = {"month": np.arange(len(d.months)), "channel": CHANNELS, "control": d.control_names}
    lags = np.stack([lag_matrix(d.x[:, i]) for i in range(len(CHANNELS))])  # (C, T, L)
    with pm.Model(coords=coords) as model:
        intercept = pm.Normal("intercept", 0.7, 0.2)
        gamma = pm.Normal("gamma", 0.0, 0.1, dims="control")
        alpha = pm.Beta("alpha", 2, 3, dims="channel")            # monthly carryover
        lam = pm.Gamma("lam", 2, 1, dims="channel")               # saturation steepness
        beta = pm.HalfNormal("beta", 0.3, dims="channel")          # max effect, share of mean sales
        sigma = pm.HalfNormal("sigma", 0.05)

        powers = pt.arange(L_MAX)
        w = alpha[:, None] ** powers[None, :]                      # (C, L)
        w = w / w.sum(axis=1, keepdims=True)
        ad = (pt.as_tensor(lags) * w[:, None, :]).sum(axis=2)      # (C, T)
        sat = 1 - pt.exp(-lam[:, None] * ad)
        contrib = pm.Deterministic("contrib", (beta[:, None] * sat).T, dims=("month", "channel"))
        mu = intercept + pt.dot(d.controls, gamma) + contrib.sum(axis=1)
        pm.Normal("y", mu, sigma, observed=d.y, dims="month")
    return model


def fit(d: Design, draws=1000, tune=1500, chains=2, seed=1, target_accept=0.95) -> az.InferenceData:
    with build_model(d):
        idata = pm.sample(draws=draws, tune=tune, chains=chains, cores=chains, random_seed=seed,
                          target_accept=target_accept, progressbar=False)
    return idata


# --------------------------------------------------------------------------- numpy twin
def media_contrib_np(x_scaled: np.ndarray, alpha, lam, beta) -> np.ndarray:
    """x_scaled (T, C); alpha/lam/beta (C,) for ONE draw. Returns (T, C) in scaled-sales units."""
    T, C = x_scaled.shape
    out = np.zeros((T, C))
    for c in range(C):
        w = alpha[c] ** np.arange(L_MAX)
        w = w / w.sum()
        ad = lag_matrix(x_scaled[:, c]) @ w
        out[:, c] = beta[c] * (1 - np.exp(-lam[c] * ad))
    return out


def _ds(idata, group: str):
    """PyMC 6 returns an xarray DataTree; older versions return InferenceData. Handle both."""
    g = idata[group]
    return g.to_dataset() if hasattr(g, "to_dataset") else g


def posterior_draws(idata) -> dict[str, np.ndarray]:
    post = _ds(idata, "posterior").stack(sample=("chain", "draw"))
    return {k: post[k].transpose("sample", ...).values for k in ("alpha", "lam", "beta")}


def counterfactuals(d: Design, idata, tv_cut_share: float = 0.15, bump: float = 0.01) -> dict:
    """Per posterior draw: contributions, marginal ROI per channel, and delta sales of the shift."""
    p = posterior_draws(idata)
    n = p["alpha"].shape[0]
    xs = d.x_raw
    tot = xs.sum(axis=0)

    # the shift: TV * (1 - s); recipients scaled up pro rata to absorb the moved budget
    moved = tv_cut_share * tot[0]
    x_shift = xs.copy()
    x_shift[:, 0] *= 1 - tv_cut_share
    x_shift[:, 1:] *= 1 + moved / tot[1:].sum()

    contrib = np.zeros((n, len(CHANNELS)))
    mroi = np.zeros((n, len(CHANNELS)))
    delta = np.zeros(n)
    for i in range(n):
        a, l, b = p["alpha"][i], p["lam"][i], p["beta"][i]
        base = media_contrib_np(xs / d.x_scale, a, l, b) * d.y_scale
        contrib[i] = base.sum(axis=0)
        for c in range(len(CHANNELS)):
            xb = xs.copy()
            xb[:, c] *= 1 + bump
            new = media_contrib_np(xb / d.x_scale, a, l, b)[:, c].sum() * d.y_scale
            mroi[i, c] = (new - contrib[i, c]) / (bump * tot[c])
        sh = media_contrib_np(x_shift / d.x_scale, a, l, b) * d.y_scale
        delta[i] = sh.sum() - base.sum()
    return {"contrib": contrib, "mroi": mroi, "delta": delta, "total_sales": float(d.y_raw.sum()),
            "spend": tot, "moved": moved}


def diagnostics(idata) -> dict:
    post = _ds(idata, "posterior")[["alpha", "lam", "beta", "intercept", "sigma"]]
    rhat = az.rhat(post)
    ess = az.ess(post)
    return {
        "max_rhat": float(max(float(rhat[v].max()) for v in rhat.data_vars)),
        "min_ess_bulk": float(min(float(ess[v].min()) for v in ess.data_vars)),
        "divergences": int(_ds(idata, "sample_stats")["diverging"].sum()),
    }
