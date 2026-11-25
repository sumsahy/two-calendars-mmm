# AI usage log

The case allows any AI tools. This log records what AI produced, what a human checked, and what was changed or rejected. The point is to show the AI was governed, not trusted blindly.

| # | Step | AI tool | What it produced | How it was checked | Outcome |
|---|---|---|---|---|---|
| 1 | Problem framing and plan | Claude (Opus 5.5) | Reading of the case, four-layer framing, traps list, phased plan | Sumukh reviewed; every scoping choice made by Sumukh from options with trade-offs (see decision log D-001 to D-007) | Accepted with Sumukh's choices |
| 2 | Package research (Robyn, Meridian) | Claude + web search | Summary of both packages and why PyMC fits ask 3 | Sourced from official repos / Google docs | Informed D-007 |
| 3 | Calendar utilities | Claude | `calendars.py` | Unit tests for 52/53-week years, Mondays only, 4-4-5 pattern; printed period-vs-month day table by hand | Accepted |
| 4 | Synthetic generator | Claude | `generator.py`, `config/scenarios.yaml` | Config committed before any fit; truth summary printed and sanity-checked (shares, ROI, sign of Δ per scenario) | Accepted |
| 5 | MMM and counterfactuals | Claude | `model.py`, `decision.py` | Test: NumPy twin equals PyMC graph (rtol 1e-6) on prior draws; decision rule boundary tests (caught a floating-point bug at P = 0.20) | Accepted after fix |
| 6 | Diagnosis of email inflation | Claude | Hypothesis that equal priors on scaled spend inflate small channels | Checked against oracle fit vs known truth; raised to Sumukh as decision D-015 rather than silently changing priors | Pending Sumukh |
| 7 | Validation gate | Claude | Profiler, verification ladder, gate runner | Adversarial tests: hallucinated quote, injection-obeying reading, week-ending switch, mid-month sales dates, unregistered file | Accepted |
| 8 | Recorded spec readings | Claude acting as the reader | 16 JSON readings | Labelled as recorded with provenance. Conflict of interest noted (same agent wrote labels); independent check = live Groq run + Sumukh label review | Accepted with caveat |
| 9 | HTML report | Claude | `report/build_html.py` | Rendered headless in light and dark; checked for console errors and label collisions; palette run through a colour-blindness validator | Accepted after two layout fixes |
| 10 | Scenario sweep and replicates | Claude (ran code) | 26 runs x 4 TV versions | Every headline number regenerated from JSON by `report/results_log.py`; counts in README re-computed by a separate script (e.g. 23 of 26) | Accepted |
| 11 | Deck (8 slides) | Claude | Slides artifact, source in `deck/project/` | Rendered locally; two layout overflows fixed; every number traced to `docs/results_log.md`; one claim narrowed ("never cleared 0.80" scoped to fair priors and simulated histories) | Accepted after fixes |
| 12 | Independent review | Separate Claude agent with no build context | Ranked findings on code, numbers and claims | See `docs/review_findings.md` | See that file |
| 13 | Fixes after independent review | Claude | Gate hardening (D-021), convergence gate (D-020), oracle-vs-truth and absolute-change tables, reworded claims | Reviewer's own repro scripts re-run against the new gate: every hole closed except units change (L-12); each now a test | Accepted; model fixes deferred by Sumukh (D-019) |
