# 00 Problem framing

Written before any model was fitted. Git history is the timestamp.

## The situation in one paragraph

Six months ago the team built a marketing mix model (MMM) for a mid-size diabetes brand. It recommended moving 15% of TV spend into digital and email. The Brand Director presented this to their VP, and it has been implemented. Three weeks into the quarterly refresh we noticed weekly totals that don't match the campaign calendar. The likely cause: TV spend arrives in **Monday-to-Sunday media weeks grouped into 4-4-5 periods**, while digital, email and sales arrive in **calendar months**. If TV was rolled up to "months" naively, the model learned from misaligned data. The Brand Director presents Q3 results in 10 days, and the TV-to-digital shift is the headline.

## The two questions

1. **Does the calendar mismatch change the recommendation the client already acted on?** And how confident are we?
2. **How do we stop it happening again** on every data refresh?

## Hypotheses

| ID | Hypothesis | How we test it |
|---|---|---|
| H1 | Naive rollups distort monthly TV materially. 5-week media periods carry 13-17% more days than their calendar month; 4-week periods carry 3-10% fewer | `aggregate.py` distortion table on synthetic data with known daily truth |
| H2 | The distortion acts like measurement error in the TV variable, which tends to **understate** TV's effect (attenuation). That biases the model toward moving money out of TV | Compare TV contribution and marginal ROI from naive vs corrected fits against the known truth |
| H3 | Whether the recommendation flips depends on how close TV and digital were at the margin. Far from the boundary, no data error flips the decision | Scenario sweep across close-call and clear-cut worlds |
| H4 | Separate from the calendar issue, the original memo used **contribution share** to justify reallocation. Reallocation should depend on **marginal ROI** at current spend | Report marginal ROI and the simulated 15% shift, not just shares |
| H5 | With about 36 monthly data points, uncertainty is wide enough that the original recommendation may never have cleared a reasonable confidence bar | Posterior intervals and P(shift helps) for every version, including the perfectly aligned oracle |

## Pre-registered decision rule (D-004, locked before fitting)

Let `Δ` = the change in total sales from cutting TV by 15% inside the analysis window and moving that money to digital and email pro rata. That is the same as asking whether the blended marginal ROI of the recipients beats TV's marginal ROI over that range of spend.

| Verdict | Condition on the posterior of `Δ` |
|---|---|
| **Holds** | P(Δ > 0) ≥ 0.80 |
| **Leans holds, not supported** | 0.50 ≤ P(Δ > 0) < 0.80 |
| **Leans reverses, not supported** | 0.20 < P(Δ > 0) < 0.50 |
| **Reverses** | P(Δ > 0) ≤ 0.20 |

The threshold of 0.80 was chosen by Sumukh (see D-004) as a business-decision standard suited to about 36 monthly data points.

## What would change our mind

* If the **corrected** model and the **oracle** model (perfectly aligned truth) disagree, the correction method itself is suspect, not just the naive one.
* If the oracle model cannot recover the true marginal ROI ordering, the problem is model or data volume, not the calendar. We would say so instead of blaming the calendar.

## Data versions compared

| Version | TV monthly series built by | Available in real life? |
|---|---|---|
| `oracle` | Summing the true **daily** TV delivery by calendar month | No, scoring only |
| `naive_445` | Summing weeks by 4-4-5 media period and calling period N "month N" | Yes, the suspected error |
| `naive_weekstart` | Assigning each whole week to the calendar month its Monday falls in | Yes, common analyst shortcut |
| `corrected` | Spreading each week's spend evenly over its 7 days, then summing by calendar month | Yes, the fix |

`corrected` assumes even delivery within a week. The synthetic truth deliberately does **not** (weekend-heavy, noisy delivery), so the fix is tested, not assumed (D-010).
