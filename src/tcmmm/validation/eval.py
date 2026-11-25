"""Score the LLM spec reader against hand-labelled specs, before and after verification.

    python -m tcmmm.validation.eval                      # recorded Claude readings
    LLM_MODE=live python -m tcmmm.validation.eval        # live Groq (needs GROQ_API_KEY)
    LLM_FIXTURE_DIR=specs/llm_fixtures_groq python -m tcmmm.validation.eval   # saved Groq run
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from .llm_spec_reader import read_spec
from .verify import verify

ROOT = Path(__file__).resolve().parents[3]
FIELDS = ["grain", "calendar_system", "week_start_day", "date_label"]


def evaluate(spec_dir: Path = ROOT / "specs" / "eval") -> dict:
    labels = yaml.safe_load((spec_dir / "labels.yaml").read_text())
    rows = []
    for name, truth in labels.items():
        spec = spec_dir / f"{name}.md"
        raw, mode = read_spec(spec)
        v = verify(name, raw, spec.read_text(), prof=None)  # spec-only: no data file for eval specs
        raw_vals = {f: raw.get("fields", {}).get(f, {}).get("value") for f in FIELDS}
        row = {"spec": name, "mode": mode, "gate": v.status}
        for f in FIELDS:
            row[f"{f}_truth"] = truth[f]
            row[f"{f}_raw_ok"] = raw_vals[f] == truth[f]
            row[f"{f}_verified_ok"] = v.accepted.get(f) == truth[f]
        # the safety property that matters: anything not aligned must never PASS
        row["unsafe_pass"] = (not truth["aligned_to_calendar_month"]) and v.status == "PASS"
        rows.append(row)
    summary = {f: {"raw_accuracy": sum(r[f"{f}_raw_ok"] for r in rows) / len(rows),
                   "verified_accuracy": sum(r[f"{f}_verified_ok"] for r in rows) / len(rows)}
               for f in FIELDS}
    summary["unsafe_passes"] = sum(r["unsafe_pass"] for r in rows)
    summary["n_specs"] = len(rows)
    return {"summary": summary, "rows": rows}


def main():
    res = evaluate()
    out = ROOT / "reports" / "validation"
    out.mkdir(parents=True, exist_ok=True)
    (out / "spec_reader_eval.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res["summary"], indent=2))
    for r in res["rows"]:
        misses = [f for f in FIELDS if not r[f"{f}_raw_ok"]]
        print(f"{r['spec']:28s} gate={r['gate']:9s} misses={misses}")


if __name__ == "__main__":
    main()
