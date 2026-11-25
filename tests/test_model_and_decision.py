import numpy as np
import pandas as pd
import pymc as pm
import pytest

from tcmmm.decision import verdict
from tcmmm.model import build_design, build_model, lag_matrix, media_contrib_np


def _toy_df(T=24, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "month": pd.date_range("2024-01-01", periods=T, freq="MS"),
        "tv_spend": rng.uniform(0, 1e6, T),
        "digital_spend": rng.uniform(3e5, 6e5, T),
        "email_spend": rng.uniform(5e4, 2e5, T),
        "net_revenue": rng.uniform(5e6, 7e6, T),
    })


def test_lag_matrix():
    m = lag_matrix(np.array([1.0, 2.0, 3.0]), 3)
    assert m.tolist() == [[1, 0, 0], [2, 1, 0], [3, 2, 1]]


def test_numpy_twin_matches_pymc_model():
    """Counterfactuals use the NumPy twin, so it must equal the PyMC graph exactly."""
    d = build_design(_toy_df())
    with build_model(d):
        prior = pm.sample_prior_predictive(draws=5, random_seed=1, var_names=["alpha", "lam", "beta", "contrib"])
    p = prior["prior"].to_dataset() if hasattr(prior["prior"], "to_dataset") else prior.prior
    for i in range(5):
        a, l, b = (p[k].isel(chain=0, draw=i).values for k in ("alpha", "lam", "beta"))
        np.testing.assert_allclose(media_contrib_np(d.x, a, l, b), p["contrib"].isel(chain=0, draw=i).values,
                                   rtol=1e-6, atol=1e-9)


@pytest.mark.parametrize("p,expected", [
    (0.80, "Holds"), (0.95, "Holds"), (0.79, "Leans holds, not supported"),
    (0.50, "Leans holds, not supported"), (0.49, "Leans reverses, not supported"),
    (0.20, "Reverses"), (0.0, "Reverses"),
])
def test_pre_registered_rule(p, expected):
    assert verdict(p) == expected
