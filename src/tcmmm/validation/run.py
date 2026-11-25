"""Refresh gate: run on EVERY data refresh, before any model is fitted.

    python -m tcmmm.validation.run --vendor-dir data/main/vendor
    python -m tcmmm.validation.eval          # score the spec reader against labelled specs

Exit code 0 = safe to proceed (PASS / WARN / TRANSFORM with conservation verified)
Exit code 2 = BLOCK, a human must look before the model refresh continues.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from ..aggregate import apportion_to_calendar_months
from .llm_spec_reader import read_spec
from .profiler import profile
from .verify import BLOCK, TRANSFORM, verify

ROOT = Path(__file__).resolve().parents[3]

# Which spec documents describe which data file. A new vendor must be registered here,
# otherwise the gate blocks: unknown sources are never joined silently.
SOURCES = {
    "tv_media_weekly.csv": "specs/vendor/tv_media_spend.md",
    "digital_monthly.csv": "specs/vendor/digital_spend.md",
    "email_monthly.csv": "specs/vendor/email_spend.md",
    "sales_monthly.csv": "specs/vendor/sales.md",
}


def check_transform(data_file: Path, v, window: tuple[pd.Timestamp, pd.Timestamp] | None) -> None:
    """Apply the registered transform on a copy, against the SALES window (the model's window):
    the weeks must cover every day of it, and spend in == spend in window + spend clipped."""
    df = pd.read_csv(data_file)
    if "week_start" not in df.columns or "tv_spend" not in df.columns:
        v.add("contract", BLOCK, "transform registered for week_start/tv_spend files only")
        return
    if "date_label=period_end" in (v.transform or ""):
        v.add("contract", BLOCK, "week-ending labels need re-keying to week start before apportioning")
        return
    ws = pd.to_datetime(df["week_start"])
    if window is None:
        v.add("contract", BLOCK, "no sales window to check TV coverage against")
        return
    start, end = window
    first_day, last_day = ws.min(), ws.max() + pd.Timedelta(days=6)
    if first_day > start or last_day < end:
        v.add("contract", BLOCK, f"TV weeks cover {first_day.date()} to {last_day.date()}, "
                                 f"but sales run {start.date()} to {end.date()}")
        return
    _, rep = apportion_to_calendar_months(df, str(start.date()), str(end.date()))
    if abs(rep["conservation_gap"]) > 0.01:
        v.add("contract", BLOCK, f"apportioning does not conserve spend (gap {rep['conservation_gap']:.2f})")
    else:
        v.add("contract", TRANSFORM, f"apportioning conserves spend to the cent "
                                     f"(total {rep['weekly_total']:,.2f})")


def sales_window(vendor_dir: Path):
    f = vendor_dir / "sales_monthly.csv"
    if not f.exists():
        return None
    m = pd.to_datetime(pd.read_csv(f)["month"])
    return m.min(), (m.max() + pd.offsets.MonthEnd(0))


def run_gate(vendor_dir: Path, sources: dict = SOURCES) -> dict:
    report = {"vendor_dir": str(vendor_dir), "sources": {}, "status": "PASS"}
    window = sales_window(vendor_dir)
    files = {p.name for p in vendor_dir.glob("*.csv")}
    for unknown in sorted(files - set(sources)):
        report["sources"][unknown] = {"status": BLOCK, "findings": [
            {"rung": "registry", "status": BLOCK, "message": "file has no registered spec; not joined"}]}
    for fname, spec_rel in sources.items():
        data_file = vendor_dir / fname
        spec_path = ROOT / spec_rel
        if not data_file.exists():
            report["sources"][fname] = {"status": BLOCK, "findings": [
                {"rung": "registry", "status": BLOCK, "message": "expected file missing"}]}
            continue
        raw, mode = read_spec(spec_path)
        prof = profile(data_file)
        v = verify(fname, raw, spec_path.read_text(), prof)
        if v.status == TRANSFORM:
            check_transform(data_file, v, window)
        d = v.to_dict()
        d["llm_mode"] = mode
        d["llm_provenance"] = raw.get("_provenance", {})
        d["profile"] = prof
        report["sources"][fname] = d
    order = ["PASS", "WARN", "TRANSFORM", "BLOCK"]
    report["status"] = max((s["status"] for s in report["sources"].values()), key=order.index)
    return report


def to_markdown(report: dict) -> str:
    lines = [f"# Refresh validation report", "", f"Vendor folder: `{report['vendor_dir']}`",
             f"**Overall: {report['status']}**", ""]
    for name, s in report["sources"].items():
        lines.append(f"## {name}: {s['status']}")
        if s.get("accepted"):
            lines.append("Verified spec claims: " + ", ".join(f"{k}={v}" for k, v in s["accepted"].items()
                                                              if not k.startswith("_")))
        if s.get("transform"):
            lines.append(f"Transform: `{s['transform']}`")
        for f in s["findings"]:
            lines.append(f"- [{f['status']}] {f['rung']}: {f['message']}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor-dir", default="data/main/vendor")
    ap.add_argument("--out", default="reports/validation")
    a = ap.parse_args()
    rep = run_gate(Path(a.vendor_dir))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "validation_report.json").write_text(json.dumps(rep, indent=2, default=str))
    (out / "validation_report.md").write_text(to_markdown(rep))
    print(to_markdown(rep))
    sys.exit(2 if rep["status"] == BLOCK else 0)


if __name__ == "__main__":
    main()
