"""Pre-registered decision rule (D-004) and result summaries."""
from __future__ import annotations

import numpy as np

THRESHOLD = 0.80  # locked before any model was fitted, chosen by Sumukh


def verdict(p_helps: float, threshold: float = THRESHOLD) -> str:
    eps = 1e-9  # guard against floating point at the boundary (1 - 0.8 != 0.2 exactly)
    if p_helps >= threshold - eps:
        return "Holds"
    if (1 - p_helps) >= threshold - eps:
        return "Reverses"
    if p_helps >= 0.5:
        return "Leans holds, not supported"
    return "Leans reverses, not supported"


def interval(a: np.ndarray, lo=5, hi=95) -> list[float]:
    return [float(np.percentile(a, lo)), float(np.percentile(a, hi))]


def summarise(cf: dict, channels=("tv", "digital", "email")) -> dict:
    total = cf["total_sales"]
    share = cf["contrib"] / total
    p_helps = float((cf["delta"] > 0).mean())
    out = {
        "contribution_share": {c: {"mean": float(share[:, i].mean()), "ci90": interval(share[:, i])}
                               for i, c in enumerate(channels)},
        "marginal_roi": {c: {"mean": float(cf["mroi"][:, i].mean()), "ci90": interval(cf["mroi"][:, i])}
                         for i, c in enumerate(channels)},
        "p_mroi_gt_tv": {c: float((cf["mroi"][:, i] > cf["mroi"][:, 0]).mean())
                         for i, c in enumerate(channels) if c != "tv"},
        "shift_delta_sales": {"mean": float(cf["delta"].mean()), "ci90": interval(cf["delta"])},
        "shift_delta_pct_of_sales": {"mean": float(cf["delta"].mean() / total),
                                     "ci90": [v / total for v in interval(cf["delta"])]},
        "p_shift_helps": p_helps,
        "verdict": verdict(p_helps),
    }
    return out
