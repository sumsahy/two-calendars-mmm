# Client handling: the 10 days before the Q3 readout

The technical fix is the easy part. The hard part is that the recommendation is already live, a senior client has presented it as "data-backed", and the next presentation is in 10 days. This note is how I would handle it as the FDE on the account.

## Principles

1. **No surprises for the client, no unverified alarm.** Tell the Brand Director early, but only after we have checked the issue on the real data. A wrong alarm costs as much trust as a missed one.
2. **Our error, our fix.** The calendar rollup was in our pipeline. We own it plainly, with the fix already in hand.
3. **Protect the client in front of their VP.** Give the Brand Director words they can use, and options, not a reversal dumped on them.
4. **Say what we know, what we don't, and what would settle it.** No false precision in either direction.

## Timeline

| Day | Action | Owner |
|---|---|---|
| 0-1 | Re-run the original model on the client's real data with the day-split TV fix. Same model, same priors, only TV changed. Also run the spend-share prior check (D-015) | FDE |
| 1 | Internal review with the engagement manager: size of change in TV and email contributions, P(shift helps) before and after | FDE + EM |
| 2 | **Call with the Brand Director** (EM leads, FDE presents). Script below | EM + FDE |
| 2-5 | Look at early Q3 actuals since the shift went live. Treat as a rough before/after read, confounded by seasonality and competitor activity | FDE |
| 5 | Agree the Q3 storyline with the Brand Director | EM |
| 6-9 | Ship the validation gate into the refresh pipeline so this cannot recur; propose a geo holdout test for TV to settle the question with an experiment | FDE |
| 10 | Brand Director presents | Client |

## What to say on day 2 (draft)

> "During the quarterly refresh our validation found that TV spend, which the agency reports in Monday-to-Sunday media weeks, was rolled up to months in a way that shifted some spend into the wrong month. We've fixed it and re-run the model. Here is what changes and what doesn't. [Insert real-data result.] The direction of the TV-to-digital shift is [still supported / no longer clearly supported]. Our confidence is [X]. For the VP readout we'd suggest presenting the shift as [a test we are monitoring / a validated move], and we've added an automated check so this can't happen again."

## Three storylines for the Q3 readout, depending on the real-data result

| Real-data result | Suggested Q3 framing |
|---|---|
| Corrected model still says **Holds** | "The shift is confirmed after a data quality review." Mention the review: it builds trust |
| Corrected model says **not supported** (most likely, based on our synthetic results) | "The shift is directionally reasonable but not yet proven. We're validating it with a geo test over Q4 before going further." Do not reverse the spend yet; do not expand it either |
| Corrected model says **Reverses** | Recommend pausing further moves out of TV and restoring part of the budget, with a holdout test. Present as the system working: the validation layer caught it |

## What I would NOT do

* Quietly patch the data and hope the numbers don't move.
* Send a written correction before talking to the Brand Director.
* Let the readout present the 15% shift as "data-backed" if the corrected model doesn't support it.
