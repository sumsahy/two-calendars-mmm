# Assumptions register

| ID | Assumption | Why | How tested / mitigated | Impact if wrong |
|---|---|---|---|---|
| A-01 | Media weeks run Monday to Sunday and are identified by their Monday | Exhibit 1 vendor spec | Profiler checks every `week_start` is a Monday; LLM reader extracts the week definition from the spec and is cross-checked | If the vendor labels weeks by their Sunday (week ending), every week shifts by 6 days. The validation gate is built to catch this |
| A-02 | 4-4-5 media periods, year starting on the Monday of the week containing 1 January, extra week in period 12 | Key terms in the case | Unit tests on 52 and 53 week years | Different vendors define the media year differently; the gate flags any vendor whose spec mentions a non-calendar period |
| A-03 | Digital, email and sales are true calendar months | Exhibit 1 | Profiler checks dates are first-of-month and spacing is 28-31 days | If sales were actually on a fiscal calendar, all channels would be misaligned, not just TV |
| A-04 | TV is delivered across the 7 days of its buying week | How weekly media buys work | The fix spreads spend evenly; truth is deliberately uneven (D-010), so we measure the residual error | Small, measured |
| A-05 | One national time series, no geo split | The case gives national files | n/a | A geo-level model (Meridian-style) would have far more data points and tighter intervals |
| A-06 | Response shapes: geometric adstock + exponential saturation | Standard in MMM literature and in Robyn, Meridian and PyMC-Marketing | Oracle fit checks the fitted model can recover truth | Misspecification would affect all versions equally; the oracle comparison isolates it |
| A-07 | The 15% moved from TV was split between digital and email in proportion to current spend | Memo does not say | Config parameter; can rerun | Changes size of Δ, not the calendar finding |
| A-08 | The analysis window is the full calendar months covered by sales; TV weeks overlapping the window edges are clipped by day in the fix | Sales are the target, so the window follows sales | Conservation test reports spend outside the window explicitly | Edge months slightly affected in naive versions; this is part of the error being reproduced |
