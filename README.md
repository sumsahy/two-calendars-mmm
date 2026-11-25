# two-calendars-mmm

**Case 3, "The Two Calendars".** A marketing mix model (MMM) for a diabetes brand recommended moving 15% of TV spend into digital and email. The client acted on it. TV spend arrives in Monday-to-Sunday media weeks on a 4-4-5 calendar; everything else arrives in calendar months. This repo answers two questions:

1. **Does the calendar mismatch change the recommendation, and how confident are we?**
2. **How do we stop it happening again on every data refresh?**

> Start here: [`docs/00_problem_framing.md`](docs/00_problem_framing.md) (hypotheses and the pre-registered decision rule), then open [`reports/before_after.html`](reports/before_after.html) in a browser.

## Answer in one screen

See [`docs/results_log.md`](docs/results_log.md) for every number and the run that produced it.

**Verdict: the 15% TV-to-digital shift is not supported by the data, and not disproven.** Hold it, don't expand it, and settle it with a geo holdout test.

| Finding | Evidence (26 simulated runs: 7 worlds + 6 extra seeds, under 2 priors) |
|---|---|
| The calendar error is large | Monthly TV off by 21% (4-4-5 period read as a month) and 18% (week-start month) of an average month; the day-split fix 1.4% |
| **The fix works** | Corrected data moves P(shift helps) by just +0.01 vs perfectly aligned data; never a confident wrong call |
| **The week-start shortcut manufactures confidence** | Raises P(shift helps) by +0.07 to +0.09 on average, above perfect data in 23 of 26 runs; called a sales-reducing shift "Holds" 4 times |
| **A second, separate issue: priors** | Equal priors credit email with 11% of sales even on perfect data (truth 4%); spend-share priors give 5% |
| **Too little data to decide** | With spend-share priors, even perfect monthly data never reached P ≥ 0.80 in 13 runs |
| Guardrail | Refresh gate: 0 of 12 tricky vendor specs passed while misaligned; adversarial tests for hallucinated quotes, prompt injection and silent week-ending switches |

Deck (8 slides): https://claude.ai/artifact/Hhify7fg5wfxRMDZzG3m4F (source in `deck/project/`).

## How it works

```
config/scenarios.yaml ──► generator (daily truth) ──► vendor files: TV weekly (media calendar), digital/email/sales monthly
                                                          │
                                            refresh gate (validation/)  ◄── LLM reads vendor specs, verified 4 ways
                                                          │  PASS / TRANSFORM / BLOCK
                                 ┌────────────┬───────────┴───────┬──────────────┐
                              oracle      naive_445        naive_weekstart     corrected
                           (truth, scoring) (period = month)  (week-start month)  (split by day)
                                 └────────────┴─────── same Bayesian MMM ───────┘
                                                          │
                         contributions, marginal ROI, P(15% shift helps) ──► pre-registered verdict
```

| Ask in the brief | Where |
|---|---|
| 1. Synthetic data with known true effects | `src/tcmmm/generator.py`, `config/scenarios.yaml` |
| 2. Reproduce the error, naive vs apportioned | `src/tcmmm/aggregate.py`, `src/tcmmm/calendars.py` |
| 3. MMM with adstock + saturation, intervals | `src/tcmmm/model.py` (PyMC) |
| 4. Does the 15% shift still hold, how confident | `src/tcmmm/decision.py`, `docs/results_log.md`, HTML report |
| 5. Validation step with an LLM, and how its flags are verified | `src/tcmmm/validation/`, `specs/`, `prompts/spec_reader.md` |
| HTML before/after view | `reports/before_after.html` |
| Validation tests | `tests/` (`make test`) |

## Run it

```bash
make install        # or open in GitHub Codespaces (devcontainer included)
make test           # unit + integration tests, no API key needed
make validate       # refresh gate on a clean vendor drop
make demo-bad-drop  # vendor silently switches to week-ending dates -> BLOCK
make eval           # score the spec reader on 12 labelled vendor specs
make fit            # main scenario, all four TV versions
make sweep replicate report   # full analysis, about 30 min on 2 cores
make llm-live       # needs GROQ_API_KEY (Codespaces secret); set GROQ_MODEL if the default is retired
```

## The validation gate in one paragraph

The data file can tell us grain and which weekday dates fall on. It cannot tell us whether a Sunday date means "week starting" or "week ending", or whether a first-of-month date is a calendar month or a fiscal month: that lives only in the vendor's spec. So an LLM reads the spec and returns structured claims with verbatim quotes. Every claim then passes four rungs: **schema** (allowed values only), **grounding** (the quote must exist in the spec), **data cross-check** (the claim must match the file's own profile) and **contract** (anything unknown blocks; weekly data must go through the day-split transform, which is re-checked to conserve spend to the cent). The LLM can only make the gate stricter, never looser.

## Decision trail

| Doc | What's in it |
|---|---|
| [`docs/decision_log.md`](docs/decision_log.md) | Every decision, options considered, trade-off, who decided |
| [`docs/assumptions.md`](docs/assumptions.md) | Assumptions and how each was tested |
| [`docs/ai_usage_log.md`](docs/ai_usage_log.md) | What AI produced, how it was checked, what was changed |
| [`docs/results_log.md`](docs/results_log.md) | Every headline number with its run and seed |
| [`docs/risks_limitations.md`](docs/risks_limitations.md) | What this does not prove |
| [`docs/client_note.md`](docs/client_note.md) | The 10 days before the Q3 readout |
| [`docs/interview_qa.md`](docs/interview_qa.md) | Likely questions, short answers |

All data is synthetic. No client data, no secrets in git.
