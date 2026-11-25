"""End-to-end runner: generate -> (validate) -> build TV versions -> fit -> decide -> save.

Usage:
    python -m tcmmm.pipeline --scenario main
    python -m tcmmm.pipeline --all
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from .aggregate import all_versions, distortion_summary, distortion_table
from .decision import summarise
from .generator import load_scenarios, write_scenario
from .model import build_design, counterfactuals, diagnostics, fit

VERSIONS = ["oracle", "naive_445", "naive_weekstart", "corrected"]


def model_frame(tv_monthly: pd.DataFrame, vendor_dir: Path) -> pd.DataFrame:
    dig = pd.read_csv(vendor_dir / "digital_monthly.csv", parse_dates=["month"])
    em = pd.read_csv(vendor_dir / "email_monthly.csv", parse_dates=["month"])
    sales = pd.read_csv(vendor_dir / "sales_monthly.csv", parse_dates=["month"])
    df = sales.merge(dig, on="month").merge(em, on="month").merge(tv_monthly, on="month", how="left")
    if df["tv_spend"].isna().any():
        raise ValueError("TV series does not cover every sales month")
    return df


def run_scenario(name: str, cfg: dict, out_root="results", data_root="data", draws=1000, tune=1500,
                 versions=VERSIONS, prior="equal") -> dict:
    t0 = time.time()
    sdir = write_scenario(name, cfg, data_root)
    vendor = sdir / "vendor"
    tv_weekly = pd.read_csv(vendor / "tv_media_weekly.csv", parse_dates=["week_start"])
    truth_daily = pd.read_csv(sdir / "_truth" / "truth_daily.csv", parse_dates=["date"])
    truth = json.loads((sdir / "_truth" / "truth_summary.json").read_text())

    tv_versions, conservation = all_versions(tv_weekly, truth_daily, cfg["start"], cfg["end"])
    out = Path(out_root) / name
    out.mkdir(parents=True, exist_ok=True)
    distortion_table(tv_versions).to_csv(out / "tv_monthly_by_version.csv")
    dist = distortion_summary(tv_versions)

    result = {
        "scenario": name,
        "prior": prior,
        "truth": {**truth, "verdict_if_known": "Helps" if truth["shift_delta_sales"] > 0 else "Hurts"},
        "conservation": conservation,
        "distortion": dist.to_dict(orient="records"),
        "versions": {},
    }
    for v in versions:
        d = build_design(model_frame(tv_versions[v], vendor))
        idata = fit(d, draws=draws, tune=tune, seed=cfg["seed"] % 10_000, prior=prior)
        cf = counterfactuals(d, idata, cfg["reallocation"]["tv_cut_share"])
        result["versions"][v] = {**summarise(cf), "diagnostics": diagnostics(idata)}
        print(f"[{name}] {v}: P(shift helps)={result['versions'][v]['p_shift_helps']:.2f} "
              f"-> {result['versions'][v]['verdict']}  ({time.time()-t0:.0f}s)", flush=True)
    result["runtime_s"] = time.time() - t0
    (out / "result.json").write_text(json.dumps(result, indent=2, default=float))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="main")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--tune", type=int, default=1500)
    ap.add_argument("--config", default="config/scenarios.yaml")
    ap.add_argument("--prior", default="equal", choices=["equal", "spend_share"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    sc = load_scenarios(a.config)
    names = list(sc) if a.all else [a.scenario]
    out = a.out or ("results" if a.prior == "equal" else f"results_{a.prior}")
    for n in names:
        run_scenario(n, sc[n], out_root=out, draws=a.draws, tune=a.tune, prior=a.prior)


if __name__ == "__main__":
    main()

