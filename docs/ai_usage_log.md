# AI usage log

The case allows any AI tools. This log records what AI produced, what a human checked, and what was changed or rejected. The point is to show the AI was governed, not trusted blindly.

| # | Step | AI tool | What it produced | How it was checked | Outcome |
|---|---|---|---|---|---|
| 1 | Problem framing and plan | Claude (Opus 5.5) | Reading of the case, four-layer framing, traps list, phased plan | Sumukh reviewed; every scoping choice made by Sumukh from options with trade-offs (see decision log D-001 to D-007) | Accepted with Sumukh's choices |
| 2 | Package research (Robyn, Meridian) | Claude + web search | Summary of both packages and why PyMC fits ask 3 | Sourced from official repos / Google docs | Informed D-007 |
| 3 | Calendar utilities | Claude | `calendars.py` | Unit tests for 52/53-week years, Mondays only, 4-4-5 pattern; printed period-vs-month day table by hand | Accepted |
| 4 | Synthetic generator | Claude | `generator.py`, `config/scenarios.yaml` | Config committed before any fit; truth summary printed and sanity-checked (shares, ROI, sign of Δ per scenario) | Accepted |
| 5 | MMM and counterfactuals | Claude | `model.py`, `decision.py` | Test: NumPy twin equals PyMC graph to 1e-9 on prior draws; decision rule boundary tests (caught a floating-point bug at P = 0.20) | Accepted after fix |
| 6 | Diagnosis of email inflation | Claude | Hypothesis that equal priors on scaled spend inflate small channels | Checked against oracle fit vs known truth; raised to Sumukh as decision D-015 rather than silently changing priors | Pending Sumukh |
| 7 | Validation gate | Claude | Profiler, verification ladder, gate runner | Adversarial tests: hallucinated quote, injection-obeying reading, week-ending switch, mid-month sales dates, unregistered file | Accepted |
| 8 | Recorded spec readings | Claude acting as the reader | 16 JSON readings | Labelled as recorded with provenance. Conflict of interest noted (same agent wrote labels); independent check = live Groq run + Sumukh label review | Accepted with caveat |
| 9 | HTML report | Claude | `report/build_html.py` | Rendered headless in light and dark; checked for console errors and label collisions; palette run through a colour-blindness validator | Accepted after two layout fixes |
