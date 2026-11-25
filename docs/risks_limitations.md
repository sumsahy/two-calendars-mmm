# Risks and limitations: what this work does NOT prove

| # | Limitation | Why it matters | What would fix it |
|---|---|---|---|
| L-01 | **Synthetic data proves the mechanism, not the client's answer** | Our verdicts describe simulated worlds. The client's real recommendation can only be judged by rerunning on their real data | Run `corrected` vs the original rollup on real data (same code path) |
| L-02 | **36 monthly data points is thin** | Intervals are wide; even perfect data (oracle) rarely clears the 0.80 bar. The original recommendation may never have been strongly supported | Weekly sales (IQVIA weekly TRx exists in pharma), geo-level data, or a geo holdout test |
| L-03 | **Few random seeds per scenario** | Time-boxed to about 3-4 worlds for the decisive scenarios and 1 for the rest. A verdict that differs between seeds is noise | More seeds overnight: `make replicate` with a higher `--seeds` |
| L-04 | **Spec-reader score is not independent** | Claude wrote both the eval labels and the recorded readings | Sumukh reviews labels; Groq live run (`make llm-live`) gives an independent reader |
| L-05 | **Model form matches the generator's family** | Adstock + saturation in both; reality may differ (e.g. halo effects, competitor spend) | Misspecification tests with a different true response shape |
| L-06 | **Prior choice drives small-channel ROI** (D-015) | Equal priors on scaled spend inflate email; spend-share priors may understate a genuinely efficient small channel | Calibrate priors with experiments (lift tests), as Meridian and Robyn support |
| L-07 | **Even-delivery assumption in the fix** | The fix spreads each week evenly over 7 days; real delivery is weekend-heavy | Measured residual error about 1-2% of an average month; daily delivery logs would remove it |
| L-08 | **Monthly adstock is coarse** | TV with a 14-day half-life mostly decays within the month | Transform at daily or weekly grain before aggregating, if sales grain allows |
| L-09 | **Some fits show a handful of divergences** | Out of 2,000 draws, 0-6 divergences; r-hat ≤ 1.01 | Higher target_accept or 4 chains on a bigger machine |
| L-10 | **Revenue, not Rx** | Pharma MMMs often model TRx/NRx | Same code; swap the target column |
