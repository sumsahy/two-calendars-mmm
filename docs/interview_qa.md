# Interview Q&A bank

Short answers first; the detail is one click away in the repo.

## Framing

**Q: What is the actual problem?**
TV arrives in Monday-to-Sunday media weeks grouped into 4-4-5 periods. Digital, email and sales arrive in calendar months. If TV is rolled up the naive way, money lands in the wrong month (5-week periods carry 13-17% more days than their month, 4-week periods 3-10% fewer), so the model learns from misaligned data.

**Q: Why build synthetic data instead of using Robyn's or Meridian's sample?**
Because the question is "which version gets closer to the truth", and only synthetic data has a known truth per channel. The sample datasets have no per-channel ground truth (D-003).

**Q: Didn't you just design the data so the naive version fails?**
Three guards. The decision rule and scenario config were committed to git before any model ran (see the first commit). The main scenario is a deliberate close call, and the sweep includes worlds where the naive version should NOT flip anything (D-009). And the truth delivers TV unevenly inside the week, so even our fix is not right by construction (D-010).

## Method

**Q: Why four versions?**
Oracle (perfect daily truth) separates model error from calendar error. If the oracle is also wrong, the problem is the model or data volume, not the calendar (D-014). Two naive versions cover the two common mistakes (D-005).

**Q: Why marginal ROI, not contribution share?**
Exhibit 2 shows contribution shares. Moving budget depends on what the next dollar earns in each channel, not on how much credit a channel gets in total. A channel can have a big share and a low marginal return because it is saturated.

**Q: Why Bayesian / why your own PyMC model?**
Ask 3 wants uncertainty intervals; Bayesian gives them natively (Robyn's ridge regression doesn't). Writing it in PyMC directly means every line is explainable and counterfactuals (the 15% shift) are computed from the same equations; a test proves the NumPy copy matches the PyMC model exactly.

**Q: Why 0.80?**
Chosen before fitting as a business-decision bar. With 36 data points, 0.90 or 0.95 would make almost everything "inconclusive", which tells the client nothing (D-004).

**Q: What was the surprise?**
Even with perfect data, the model inflated email (about 11% of sales vs a true 4%). Equal priors on spend scaled by each channel's average quietly assume a dollar of email is worth much more than a dollar of TV. That biases any model toward "move money into small channels", independent of the calendar bug (D-015).

## The LLM part

**Q: Why use an LLM at all? Couldn't you just check the data?**
The data can tell you grain and which weekday dates fall on. It cannot tell you whether a Sunday date means "week starting Sunday" or "week ending Sunday", or whether a first-of-month date is a calendar month or a fiscal month. Those facts live only in the vendor spec, which is free text. The LLM reads what the data can't say; the data checks what the LLM can't be trusted to say.

**Q: How do you know the LLM is right?**
Four rungs: schema (allowed values only), grounding (every claim must quote the spec verbatim; quotes are checked), data cross-check (claims must match the file's own profile), contract (anything unknown blocks). The LLM can only make the gate stricter, never looser. Tests prove a hallucinated quote is discarded, an LLM that obeys an injected instruction is overruled, and a silent switch to week-ending dates is blocked.

**Q: What if the LLM is down or the key is missing?**
Recorded mode. CI runs on recorded readings, so the gate never depends on an API being up. Live mode is for refreshing readings when a spec changes.

**Q: Is your 12/12 eval score meaningful?**
Not on its own: Claude wrote both the labels and the recorded readings. That's stated in the report. The independent check is the live Groq run plus a human review of the labels (L-04).

## Client

**Q: The Brand Director presents in 10 days. What do you do?**
Verify on real data first (day 0-1), tell the EM, then the Brand Director on day 2 with options and a script, not a reversal. See `docs/client_note.md`.

**Q: If the corrected model says "not supported", do you tell them to reverse the shift?**
No. "Not supported" is not "wrong". Hold the shift where it is, don't expand it, and run a geo holdout to settle it with an experiment.
