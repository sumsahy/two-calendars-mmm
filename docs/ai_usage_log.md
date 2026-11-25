# AI usage log

The case allows any AI tools. This log records what AI produced, what a human checked, and what was changed or rejected. The point is to show the AI was governed, not trusted blindly.

| # | Step | AI tool | What it produced | How it was checked | Outcome |
|---|---|---|---|---|---|
| 1 | Problem framing and plan | Claude (Opus 5.5) | Reading of the case, four-layer framing, traps list, phased plan | Sumukh reviewed; every scoping choice made by Sumukh from options with trade-offs (see decision log D-001 to D-007) | Accepted with Sumukh's choices |
| 2 | Package research (Robyn, Meridian) | Claude + web search | Summary of both packages and why PyMC fits ask 3 | Sourced from official repos / Google docs | Informed D-007 |
| 3 | Calendar utilities | Claude | `calendars.py` | Unit tests for 52/53-week years, Mondays only, 4-4-5 pattern; printed period-vs-month day table by hand | Accepted |
| 4 | Synthetic generator | Claude | `generator.py`, `config/scenarios.yaml` | Config committed before any fit; truth summary printed and sanity-checked (shares, ROI, sign of Δ per scenario) | Accepted |
