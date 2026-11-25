"""The validation gate must catch what the LLM gets wrong, not just repeat what it says."""
import copy
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from tcmmm.generator import load_scenarios, write_scenario
from tcmmm.validation.eval import evaluate
from tcmmm.validation.profiler import profile
from tcmmm.validation.run import run_gate
from tcmmm.validation.verify import BLOCK, PASS, TRANSFORM, is_grounded, verify

ROOT = Path(__file__).resolve().parents[1]
TV_SPEC = (ROOT / "specs/vendor/tv_media_spend.md").read_text()
TV_FIX = json.loads((ROOT / "specs/llm_fixtures/tv_media_spend.json").read_text())


@pytest.fixture(scope="module")
def vendor_dir(tmp_path_factory):
    cfg = load_scenarios(ROOT / "config/scenarios.yaml")["main"]
    out = write_scenario("main", cfg, tmp_path_factory.mktemp("data"))
    return out / "vendor"


# ------------------------------------------------------------------ happy path
def test_gate_on_clean_refresh_requires_transform_not_block(vendor_dir):
    rep = run_gate(vendor_dir)
    assert rep["status"] == TRANSFORM
    assert rep["sources"]["tv_media_weekly.csv"]["status"] == TRANSFORM
    for f in ("digital_monthly.csv", "email_monthly.csv", "sales_monthly.csv"):
        assert rep["sources"][f]["status"] == PASS


def test_profiler_reads_grain_from_data(vendor_dir):
    p = profile(vendor_dir / "tv_media_weekly.csv")
    assert p["grain"] == "weekly" and p["dominant_weekday"] == "monday"
    assert profile(vendor_dir / "sales_monthly.csv")["grain"] == "monthly"


# ------------------------------------------------------------------ rung 1: schema
def test_malformed_llm_output_blocks(vendor_dir):
    v = verify("tv", {"source_name": "x"}, TV_SPEC, profile(vendor_dir / "tv_media_weekly.csv"))
    assert v.status == BLOCK


def test_out_of_vocabulary_value_blocks(vendor_dir):
    bad = copy.deepcopy(TV_FIX)
    bad["fields"]["grain"]["value"] = "fortnightly"
    assert verify("tv", bad, TV_SPEC, profile(vendor_dir / "tv_media_weekly.csv")).status == BLOCK


# ------------------------------------------------------------------ rung 2: grounding
def test_hallucinated_evidence_is_discarded(vendor_dir):
    bad = copy.deepcopy(TV_FIX)
    bad["fields"]["date_label"]["evidence"] = "Rows are keyed by the Sunday that ends each week."
    v = verify("tv", bad, TV_SPEC, profile(vendor_dir / "tv_media_weekly.csv"))
    assert v.accepted["date_label"] == "unknown"
    assert v.status == BLOCK  # weekly + unknown label = cannot place days in months safely


def test_grounding_tolerates_markdown_and_case():
    assert is_grounded("the week_start column holds the monday that begins the buying week", TV_SPEC)
    assert not is_grounded("weeks run Sunday to Saturday", TV_SPEC)


# ------------------------------------------------------------------ rung 3: data cross-check
def test_llm_that_obeys_an_injection_is_overruled(vendor_dir):
    """Compromised reading: LLM claims the weekly TV file is calendar-monthly."""
    prof = profile(vendor_dir / "tv_media_weekly.csv")
    # (a) its quote doesn't support "monthly": claim discarded, gate falls back to the data and never PASSes
    c1 = copy.deepcopy(TV_FIX)
    c1["fields"]["grain"] = {"value": "monthly", "evidence": "Data is delivered weekly.", "confidence": 1}
    c1["fields"]["calendar_system"] = {"value": "gregorian", "evidence": "", "confidence": 1}
    v1 = verify("tv", c1, TV_SPEC, prof)
    assert v1.accepted["grain"] == "unknown" and v1.status != PASS
    # (b) a real quote that mentions months: grounded, but the data says weekly -> BLOCK
    c2 = copy.deepcopy(TV_FIX)
    c2["fields"]["grain"] = {"value": "monthly", "evidence": "so periods do not line up with calendar months",
                             "confidence": 1}
    v2 = verify("tv", c2, TV_SPEC, prof)
    assert v2.status == BLOCK
    assert any("data is 'weekly'" in f.message for f in v2.findings)


def test_vendor_silently_switches_to_week_ending_dates(vendor_dir, tmp_path):
    """New drop: same spec, but dates are now the Sunday that ends each week."""
    drop = tmp_path / "vendor"
    shutil.copytree(vendor_dir, drop)
    tv = pd.read_csv(drop / "tv_media_weekly.csv", parse_dates=["week_start"])
    tv["week_start"] = (tv["week_start"] + pd.Timedelta(days=6)).dt.strftime("%Y-%m-%d")
    tv.to_csv(drop / "tv_media_weekly.csv", index=False)
    rep = run_gate(drop)
    assert rep["status"] == BLOCK
    msgs = [f["message"] for f in rep["sources"]["tv_media_weekly.csv"]["findings"]]
    assert any("data dates fall on sunday" in m for m in msgs)


def test_sales_with_mid_month_dates_blocks(vendor_dir, tmp_path):
    drop = tmp_path / "vendor"
    shutil.copytree(vendor_dir, drop)
    s = pd.read_csv(drop / "sales_monthly.csv", parse_dates=["month"])
    s["month"] = (s["month"] + pd.Timedelta(days=14)).dt.strftime("%Y-%m-%d")
    s.to_csv(drop / "sales_monthly.csv", index=False)
    assert run_gate(drop)["sources"]["sales_monthly.csv"]["status"] == BLOCK


# ------------------------------------------------------------------ rung 4: contract
def test_fiscal_month_file_cannot_join_as_calendar_month():
    spec = (ROOT / "specs/eval/e05_digital_fiscal_445.md").read_text()
    raw = json.loads((ROOT / "specs/llm_fixtures/e05_digital_fiscal_445.json").read_text())
    assert verify("e05", raw, spec, prof=None).status == BLOCK


def test_unregistered_file_blocks(vendor_dir, tmp_path):
    drop = tmp_path / "vendor"
    shutil.copytree(vendor_dir, drop)
    (drop / "ctv_weekly.csv").write_text("week_start,ctv_spend\n2025-01-06,100\n")
    assert run_gate(drop)["sources"]["ctv_weekly.csv"]["status"] == BLOCK


# ------------------------------------------------------------------ eval harness
def test_no_misaligned_spec_ever_passes():
    res = evaluate()
    assert res["summary"]["unsafe_passes"] == 0
    assert res["summary"]["n_specs"] == 12


# ------------------------------------------------------------------ added after the independent review (R-03)
@pytest.mark.parametrize("quote", [
    "The `week_start` column holds the Sunday that begins the buying week.",   # one-word swap
    "The `week_start` column holds the Monday that ends the buying week.",     # one-word swap
    "Each row is one vendor media-buying week, running Sunday to Saturday.",
    "Sunday", "weekly",                                                         # too short to prove anything
])
def test_near_miss_quotes_are_not_grounded(quote):
    assert not is_grounded(quote, TV_SPEC)


def test_real_quote_that_does_not_support_the_value_is_discarded(vendor_dir, tmp_path):
    """Week-ending drop + LLM claims week starts Sunday, quoting a REAL sentence that says Monday."""
    drop = tmp_path / "vendor"
    shutil.copytree(vendor_dir, drop)
    tv = pd.read_csv(drop / "tv_media_weekly.csv", parse_dates=["week_start"])
    tv["week_start"] = (tv["week_start"] + pd.Timedelta(days=6)).dt.strftime("%Y-%m-%d")
    tv.to_csv(drop / "tv_media_weekly.csv", index=False)
    bad = copy.deepcopy(TV_FIX)
    bad["fields"]["week_start_day"] = {"value": "sunday", "evidence": "running Monday to Sunday", "confidence": 0.9}
    v = verify("tv", bad, TV_SPEC, profile(drop / "tv_media_weekly.csv"))
    assert v.accepted["week_start_day"] == "unknown"
    assert v.status == BLOCK


def test_llm_cannot_pass_a_fiscal_month_file_as_calendar_month(vendor_dir):
    spec = (ROOT / "specs/eval/e05_digital_fiscal_445.md").read_text()
    raw = json.loads((ROOT / "specs/llm_fixtures/e05_digital_fiscal_445.json").read_text())
    raw["fields"]["calendar_system"] = {"value": "gregorian", "confidence": 0.9,
                                        "evidence": "The month column shows the first day of the matching calendar month"}
    assert verify("e05", raw, spec, profile(vendor_dir / "digital_monthly.csv")).status == BLOCK


def test_injection_is_flagged_without_relying_on_the_llm():
    spec = (ROOT / "specs/eval/e11_injection.md").read_text()
    raw = json.loads((ROOT / "specs/llm_fixtures/e11_injection.json").read_text())
    raw["risks"] = []  # a reader that failed to mention it
    v = verify("e11", raw, spec, prof=None)
    assert any(f.rung == "spec_scan" and "automated readers" in f.message for f in v.findings)


def _drop(vendor_dir, tmp_path, fn):
    d = tmp_path / "vendor"
    shutil.copytree(vendor_dir, d)
    fn(d)
    return run_gate(d)


def test_a_few_off_weekday_rows_block(vendor_dir, tmp_path):
    def f(d):
        tv = pd.read_csv(d / "tv_media_weekly.csv", parse_dates=["week_start"])
        tv.loc[tv.index[::60], "week_start"] += pd.Timedelta(days=1)
        tv["week_start"] = tv["week_start"].dt.strftime("%Y-%m-%d")
        tv.to_csv(d / "tv_media_weekly.csv", index=False)
    assert _drop(vendor_dir, tmp_path, f)["sources"]["tv_media_weekly.csv"]["status"] == BLOCK


def test_negative_or_missing_spend_blocks(vendor_dir, tmp_path):
    def f(d):
        tv = pd.read_csv(d / "tv_media_weekly.csv")
        tv.loc[5, "tv_spend"] = -1e7
        tv.loc[6, "tv_spend"] = float("nan")
        tv.to_csv(d / "tv_media_weekly.csv", index=False)
    assert _drop(vendor_dir, tmp_path, f)["sources"]["tv_media_weekly.csv"]["status"] == BLOCK


def test_tv_that_does_not_cover_the_sales_window_blocks(vendor_dir, tmp_path):
    def f(d):
        tv = pd.read_csv(d / "tv_media_weekly.csv")
        tv.iloc[:80].to_csv(d / "tv_media_weekly.csv", index=False)
    rep = _drop(vendor_dir, tmp_path, f)
    assert rep["sources"]["tv_media_weekly.csv"]["status"] == BLOCK
    assert any("sales run" in x["message"] for x in rep["sources"]["tv_media_weekly.csv"]["findings"])


def test_eval_no_misaligned_spec_passes_or_gets_a_wrong_transform():
    s = evaluate()["summary"]
    assert s["unsafe_passes"] == 0 and s["n_misaligned"] == 9
