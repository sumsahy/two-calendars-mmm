# Solution Document: Case 3, The Two Calendars

Author: Sumukh (FDE associate). Repository: `sumsahy/two-calendars-mmm`. Every number below is regenerated from `results*/**/result.json` into `docs/results_log.md`.

## 1. Solution overview

TV spend arrives in Monday-to-Sunday media weeks grouped into 4-4-5 periods, while digital, email and sales arrive in calendar months; the client's MMM, which recommended moving 15% of TV into digital and email, was fit on TV rolled up to months without reconciling the two calendars. I built a synthetic diabetes-brand world with a known true effect per channel, reproduced two naive rollups (4-4-5 period read as a month: 21% average monthly TV error; whole week to its start month: 18%) against a day-apportioned fix (1.4%), and fit the same Bayesian MMM (PyMC, adstock + saturation) on every version across 26 runs. The fix tracks perfectly aligned data (mean change in P(shift helps) +0.01, never a confident wrong call), while the week-start shortcut inflates confidence in the shift in 22 of 25 runs and four times called a sales-reducing shift "Holds". An independent review also showed the monthly model itself recovers only about half of TV's true marginal ROI on perfect data, so **the 15% shift is not supported and not disproven**: hold it, do not expand it, and settle it with a geo test. To prevent recurrence I built a refresh gate in which an LLM reads vendor specs and deterministic checks verify every claim; 0 of 9 misaligned test specs got through.

## 2. Approach and methodology

| Step | What | Why | Where |
|---|---|---|---|
| 1 | Pre-register the decision rule and scenarios in git before any fit: the shift **Holds** if P(15% shift raises sales) ≥ 0.80, **Reverses** if ≤ 0.20, otherwise "not supported" | Stops us tuning the test to get a story | `docs/00_problem_framing.md`, `config/scenarios.yaml`, first commit |
| 2 | Simulate truth at **daily** grain, then write vendor files the way vendors deliver them | Only synthetic data has a known truth per channel | `src/tcmmm/generator.py` |
| 3 | Build four monthly TV series: `oracle` (true daily delivery, scoring only), `naive_445`, `naive_weekstart`, `corrected` (spread each week over 7 days, clip to window, sum by calendar month; spend conserved to the cent) | Oracle separates calendar error from model error | `src/tcmmm/aggregate.py`, `src/tcmmm/calendars.py` |
| 4 | Fit one Bayesian MMM per version: monthly geometric adstock (3-month window), exponential saturation, trend, yearly Fourier terms, January dummy (insurance reset); 2 chains, NUTS | Intervals are needed to say "how confident" | `src/tcmmm/model.py` |
| 5 | Compute per posterior draw: contribution share, marginal ROI (+1% spend), and Δsales of the actual 15% shift (TV × 0.85, money pro rata to digital and email) | Budget moves depend on marginal ROI, not contribution share (Exhibit 2's metric) | `model.py::counterfactuals`, `decision.py` |
| 6 | Sweep 7 scenarios × 2 priors, plus 3 extra seeds for the two decisive worlds (26 runs × 4 versions) | One synthetic history is an anecdote | `pipeline.py`, `replicate.py` |
| 7 | Refresh gate: profile each file, LLM reads its spec, five-rung verification, block on anything unknown | Prevents recurrence on every refresh | `src/tcmmm/validation/` |
| 8 | Independent review by a separate agent with no build context; findings dispositioned | The work should not grade itself | `docs/review_findings.md` |

## 3. How you arrived at it

**Alternatives considered and rejected** (full log: `docs/decision_log.md`, D-001 to D-021):

| Decision | Chosen | Rejected and why |
|---|---|---|
| Data | Own synthetic, daily truth (D-003) | Robyn and Meridian sample data: no per-channel ground truth to score against |
| Model | Own PyMC model with a NumPy twin for counterfactuals (D-007/D-008) | PyMC-Marketing `MMM` class: internal rescaling makes the 15% counterfactual fiddly; Robyn: ridge regression gives no posterior intervals |
| Decision bar | 0.80 (D-004) | 0.90 / 0.95: near-certain "inconclusive" with 36 monthly points |
| Naive rollups | Both (D-005) | Only one would miss a common failure mode |
| Main scenario | Deliberate close call, plus sweep (D-009) | Far-from-boundary worlds cannot show whether an error flips a decision |
| Prior | Spend-share as main, equal as sensitivity (D-015) | Equal priors inflate the smallest channel. **Chosen after seeing equal-prior results (disclosed, L-11)** |
| After review | No rerun; disclose model bias (D-019) | Daily-grain refit (option A) did not fit the time box |
| LLM role | Advisory only; gate can only get stricter (D-017, D-021) | LLM as decision-maker: a guardrail an LLM can loosen is not a guardrail |

**Key assumptions** (`docs/assumptions.md`): media weeks are Monday-keyed; media year starts on the Monday of the week containing 1 January, 4-4-5 periods, 53rd week in period 12; digital, email and sales are true calendar months; the moved 15% splits pro rata between digital and email (memo silent); sales = monthly net revenue.

**Clarification Desk answers:** none were received during the session; the case pages were the only source. Where the case was silent, the assumption is logged above.

## 4. Data

Generated by `src/tcmmm/generator.py` from `config/scenarios.yaml` (fixed seed 20261125). Window: Jan 2023 to Dec 2025 (36 months; 24 in `two_years_only`), plus 120 days of burn-in.

| Element | How it is generated | True value (main scenario) |
|---|---|---|
| TV | Weekly buys in flights of 3-7 weeks on, 2-5 off, about $250K per on-week; delivered across the week with weekend weight 1.35 and 15% day noise (so the fix is not right by construction) | Half-life 14 days, avg ROI 1.6, mROI 0.98, 15.6% of sales |
| Digital | Monthly, about $450K, correlation 0.3 with TV | Half-life 5 days, avg ROI 1.7, mROI 1.16, 10.7% of sales |
| Email | Monthly, about $120K | Half-life 3 days, avg ROI 2.5, mROI 1.90, 4.2% of sales |
| Baseline | $150K/day, +4%/yr, ±5% seasonality, −8% January (insurance reset) | |
| Sales | Monthly net revenue with 3% multiplicative noise | |
| Truth of the 15% shift | Simulated on the daily truth | **+0.28% of sales** (main); **−0.30%** in `tv_clearly_better` |

Vendor files: `data/<scenario>/vendor/` (`tv_media_weekly.csv` with `week_start`, `media_year`, `media_period`; three monthly CSVs). Truth: `data/<scenario>/_truth/truth_summary.json` (never read by the model code).

**Limitations of the data:** synthetic data proves the mechanism, not the client's answer; the 7 scenarios share one random seed (same flighting draws); response curves come from the same family the model assumes; one national series, no geos.

## 5. Evaluation

**Metrics:** monthly TV error vs true delivery; P(shift helps) and the pre-registered verdict per version; change in P vs the oracle (signed and absolute); recovery of true contribution share and marginal ROI; convergence (fits with r-hat > 1.05 or > 20 divergences are excluded from tallies, D-020); for the gate, misaligned specs that get through.

**Results** (`docs/results_log.md`):

| Metric | naive_445 | naive_weekstart | corrected |
|---|---|---|---|
| Mean abs monthly TV error (main) | 21.0% | 18.1% | 1.4% |
| Mean change in P vs oracle, spend-share (13 runs) | −0.08 | **+0.09** | +0.01 |
| Mean absolute change in P vs oracle, spend-share | 0.09 | 0.10 | 0.03 |
| Runs where P exceeds oracle (both priors, converged) | | **22 of 25** | |
| Confident WRONG verdicts (both priors) | 0 | **4** | **0** |

| Model-level finding | Value |
|---|---|
| Spend-share prior: runs where even the oracle reached P ≥ 0.80 | 0 of 13 |
| TV mROI recovered on perfect data (median, 26 runs) | **49% of truth** |
| Email share on perfect data, equal prior / spend-share / truth | 11.1% / 5.0% / 4.2% |
| Email mROI on perfect data, spend-share vs truth | 1.12 vs 1.90 |
| Equal-prior oracle: confident wrong "Holds" | 1 |
| Gate: misaligned specs that passed, only warned, or got a wrong transform | **0 of 9** (12 specs) |
| Tests | 49 passing (`make test`), CI on every push |

**Uncertainty:** 90% posterior intervals are wide (main, corrected: TV share 3.4% to 21.4%; TV mROI 0.16 to 1.18). Monte Carlo SE of each P is about 0.02, so differences under 0.05 are noise. Excluded for non-convergence: `main__seed3 / naive_445` (r-hat 1.52), `high_tv_digital_corr / oracle` (equal prior).

**Mid-session update:** none received during the session. The material change during the work came from the **independent review**: it found the oracle bias, a shrinking saturation prior, three ways the LLM could loosen the gate, an eval metric that could not fail, and unconverged fits in tallies. Gate and eval were fixed and tested; the model bias became a headline finding instead of a rerun (D-019). See `docs/review_findings.md`.

## 6. Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.13 (CI on 3.12) |
| Modelling | PyMC 6.4.0, ArviZ 1.3.0, NumPy 2.5, pandas 3.0 |
| Validation | pydantic 2.13 (LLM output schema), httpx 0.28 (Groq API), regex rules, pytest |
| Report | Self-contained HTML + vanilla JS/SVG (no CDN), rendered and checked headless in Chrome via Playwright |
| Infra | GitHub repo + GitHub Actions CI; Codespaces devcontainer; `Makefile` entry points |
| LLM in the pipeline | **Groq API, `llama-3.3-70b-versatile`** (configurable via `GROQ_MODEL`), temperature 0, JSON mode, prompt `prompts/spec_reader.md` (SHA stored with each reading). **Not yet run live** (pending API key) |
| LLM for recorded readings | **Anthropic Claude Opus 5.5** (`claude-opus-5-5`), in-session, following the same prompt; labelled `"mode": "recorded"` with provenance in `specs/llm_fixtures/*.json` |
| AI assistance for the build | Anthropic Claude Opus 5.5 wrote code and docs under Sumukh's direction; a separate Claude Opus 5.5 agent did the independent review. Governance log: `docs/ai_usage_log.md` |

## 7. Use of LLMs

**Where and why.** One place: reading free-text vendor specifications in `src/tcmmm/validation/llm_spec_reader.py`. The data file can reveal grain and which weekday dates fall on; it cannot reveal whether a Sunday date means "week starting" or "week ending", or whether a first-of-month date is a calendar month or a fiscal month. That lives only in prose that varies by vendor, which is where an LLM beats hand-written rules. The LLM never changes data and never decides alone.

**Grounding** (`src/tcmmm/validation/verify.py`), five rungs:
1. Schema: fixed fields and allowed values only.
2. Grounding: each claim must quote the spec verbatim (normalised, at least two words) **and** the quote must itself support the value (deterministic keyword rules). A one-word swap fails.
3. Spec scan: an independent rule-based reader extracts the same facts; any disagreement blocks.
4. Data check: claims must match the file's profile (spacing, weekday purity, gaps, bad values, coverage of the sales window).
5. Contract: unknown blocks; weekly data must go through the day-split transform, re-checked for spend conservation; a monthly file vouched for only by the LLM goes to human review.

**Evaluation:** 12 labelled specs (`specs/eval/`) covering week-ending labels, Sunday-Saturday weeks, fiscal 4-4-5, broadcast months, daily data, an ambiguous spec, a prompt injection and a mid-series grain change. Field accuracy 92% to 100%; 0 of 9 misaligned specs got through. **Caveat:** Claude wrote both the labels and the recorded readings, so this is not independent; `make llm-live` (Groq) plus a human label review is the independent check.

**Known failure modes:** hallucinated or paraphrased quotes (discarded); quotes that exist but do not say the value (discarded); following instructions embedded in a spec (detected by the spec scan, overruled by data); over-confident defaults when a spec is silent (forced to "unknown", which blocks); model deprecation on Groq (model name configurable); API down (recorded mode keeps CI running). Not caught: a vendor silently changing units (L-12).

## 8. Limitations and next steps

**Limitations** (`docs/risks_limitations.md`, L-01 to L-13): synthetic results show the mechanism, not the client's answer; 36 monthly points cannot settle the decision; the monthly model under-credits TV on perfect data (about 49%); the saturation prior shrinks marginal ROI; the main prior was chosen post hoc; few seeds, shared across scenarios; some priors sit near the truth; gate cannot detect unit changes.

**Next steps for the client (10 days):** rerun on real data with the day-split fix (days 0-1); brief the Brand Director with the engagement manager, options not a reversal (day 2); agree a Q3 story of "directionally reasonable, now being validated" unless real data says otherwise (day 5); put the gate into every refresh, design a geo holdout for TV, request weekly sales (days 6-9). Details: `docs/client_note.md`. Model next step: daily-grain TV response before summing to months, looser saturation prior, lift-test calibration.

**For a real deployment:**
- *Data privacy:* MMM inputs are aggregate spend and sales (no patient or HCP data), but sales are commercially sensitive. Run inside the client's cloud tenant; send the LLM **only spec documents**, never data; use a provider with zero-retention terms or a model hosted in the client's environment.
- *Security:* API keys in a secrets manager (Codespaces/Actions secrets here, never in git); least-privilege service account for vendor drops; treat vendor specs as untrusted input (injection scan already in place); pin dependency versions.
- *Monitoring:* gate status per refresh with alerting on BLOCK; drift checks on spend totals vs the previous accepted refresh (closes L-12); track LLM agreement with the spec scan over time; convergence diagnostics as a hard gate on model refresh; re-evaluate the spec reader whenever the prompt or model version changes (prompt SHA stored).

## 9. Submission index

| File / folder | What it is | How to run |
|---|---|---|
| `README.md` | Entry point, answer in one screen | |
| `SOLUTION.md` | This document | |
| `config/scenarios.yaml` | True parameters of every simulated world | |
| `src/tcmmm/calendars.py` | 4-4-5 media calendar utilities | |
| `src/tcmmm/generator.py` | **Data generator** (daily truth, vendor files) | `make data` |
| `src/tcmmm/aggregate.py` | Two naive rollups and the day-split fix | |
| `src/tcmmm/model.py`, `decision.py` | PyMC MMM, counterfactuals, pre-registered rule | `make fit` |
| `src/tcmmm/pipeline.py`, `replicate.py` | Sweep and seed replication (gate runs first) | `make sweep sweep-equal replicate` (about 30 min, 2 cores) |
| `src/tcmmm/validation/` | Refresh gate: profiler, LLM reader, verification, runner, eval | `make validate`, `make demo-bad-drop`, `make eval`, `make llm-live` |
| `prompts/spec_reader.md` | LLM prompt | |
| `specs/vendor/`, `specs/eval/`, `specs/llm_fixtures/` | Vendor specs, 12 labelled eval specs, recorded readings | |
| `tests/` | **Validation tests** (49) | `make test` |
| `reports/before_after.html` | **HTML before-and-after view** (offline, light/dark, table views) | `make report`, open in a browser |
| `reports/validation/` | Gate report and spec-reader eval | |
| `results/`, `results_spend_share/` | Per-run JSON (equal / spend-share prior) | |
| `deck/project/` | 8-slide deck source (live deck: https://claude.ai/artifact/Hhify7fg5wfxRMDZzG3m4F) | |
| `docs/` | Framing, decision log, assumptions, AI usage log, results log, review findings, limitations, client note, interview Q&A | |
| `Makefile`, `.github/workflows/ci.yml`, `.devcontainer/` | One-command runs, CI, Codespaces | `make install` then `make all` |
