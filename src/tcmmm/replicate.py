"""Replicate scenarios across several random worlds (different seeds, same true parameters).

One seed is one synthetic history. A verdict that flips between seeds is noise, not a finding.

    python -m tcmmm.replicate --scenarios main tv_clearly_better --seeds 5
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .generator import load_scenarios
from .pipeline import run_scenario


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", nargs="+", default=["main", "tv_clearly_better"])
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--config", default="config/scenarios.yaml")
    ap.add_argument("--prior", default="equal", choices=["equal", "spend_share"])
    ap.add_argument("--draws", type=int, default=600)
    ap.add_argument("--tune", type=int, default=800)
    a = ap.parse_args()
    root = Path("results/replicates" if a.prior == "equal" else f"results_{a.prior}/replicates")
    sc = load_scenarios(a.config)
    for name in a.scenarios:
        for k in range(1, a.seeds + 1):  # seed offset 0 is the sweep run itself
            cfg = dict(sc[name])
            cfg["seed"] = sc[name]["seed"] + 1000 * k
            run_scenario(f"{name}__seed{k}", cfg, out_root=root, data_root="data/replicates", prior=a.prior,
                         draws=a.draws, tune=a.tune)
    rows = []
    for p in sorted(root.glob("*/result.json")):
        r = json.loads(p.read_text())
        for v, res in r["versions"].items():
            rows.append({"run": r["scenario"], "version": v, "p_shift_helps": res["p_shift_helps"],
                         "verdict": res["verdict"], "truth": r["truth"]["verdict_if_known"]})
    (root / "summary.json").write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
