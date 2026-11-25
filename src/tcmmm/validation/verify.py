"""Verification ladder for LLM spec readings, and the refresh gate.

    rung 1  SCHEMA     the LLM output parses and uses allowed values         -> else BLOCK
    rung 2  GROUNDING  every quoted evidence string exists in the spec text   -> else claim discarded
    rung 3  DATA       claims agree with the deterministic profile of the file -> else BLOCK
    rung 4  CONTRACT   source can reach Gregorian calendar months safely:
                         aligned           -> PASS
                         known transform   -> TRANSFORM (apportion by day), conservation re-checked
                         anything unknown  -> BLOCK, route to a human

The LLM never changes data. It can only make the gate stricter, never looser:
a BLOCK from the data profile stands even if the LLM says everything is fine.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass, field

from pydantic import ValidationError

from .llm_spec_reader import SpecReading
from .profiler import WEEKDAYS

PASS, WARN, TRANSFORM, BLOCK = "PASS", "WARN", "TRANSFORM", "BLOCK"
_ORDER = {PASS: 0, WARN: 1, TRANSFORM: 2, BLOCK: 3}


@dataclass
class Finding:
    rung: str
    status: str
    message: str


@dataclass
class Verdict:
    source: str
    status: str = PASS
    findings: list[Finding] = field(default_factory=list)
    accepted: dict = field(default_factory=dict)  # claims that survived verification
    transform: str | None = None

    def add(self, rung: str, status: str, message: str):
        self.findings.append(Finding(rung, status, message))
        if _ORDER[status] > _ORDER[self.status]:
            self.status = status

    def to_dict(self):
        return asdict(self)


# ----------------------------------------------------------------- rung 2 helper
def _norm(s: str) -> str:
    s = s.lower().replace("–", "-").replace("—", "-")
    s = re.sub(r"[`*_|#>]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def is_grounded(quote: str, spec_text: str, min_ratio: float = 0.92) -> bool:
    """True if the quote appears in the spec, allowing whitespace/markdown/case differences."""
    q, t = _norm(quote), _norm(spec_text)
    if not q:
        return False
    if q in t:
        return True
    n = len(q)
    best = 0.0
    step = max(1, n // 8)
    for i in range(0, max(1, len(t) - n + 1), step):
        r = difflib.SequenceMatcher(None, q, t[i : i + n]).ratio()
        best = max(best, r)
        if best >= min_ratio:
            return True
    return False


# ----------------------------------------------------------------- the ladder
def verify(source: str, raw: dict, spec_text: str, prof: dict | None) -> Verdict:
    v = Verdict(source)

    # rung 1: schema
    try:
        reading = SpecReading.model_validate({k: val for k, val in raw.items() if not k.startswith("_")})
    except ValidationError as e:
        v.add("schema", BLOCK, f"LLM output did not match schema: {e.errors()[:2]}")
        return v
    for err in reading.validate_enums():
        v.add("schema", BLOCK, f"LLM used a value outside the allowed set: {err}")
    if v.status == BLOCK:
        return v

    # rung 2: grounding
    for name in ("grain", "calendar_system", "week_start_day", "date_label"):
        claim = getattr(reading.fields, name)
        if claim.value in ("unknown", "not_applicable"):
            v.accepted[name] = claim.value
            continue
        if is_grounded(claim.evidence, spec_text):
            v.accepted[name] = claim.value
        else:
            v.accepted[name] = "unknown"
            v.add("grounding", WARN, f"{name}={claim.value!r} discarded: evidence quote not found in spec "
                                     f"({claim.evidence[:60]!r})")
    for r in reading.risks:
        if r.issue == "instruction_in_spec":
            v.add("grounding", WARN, "spec contains text addressed to automated readers; it was not followed")

    # rung 3: data cross-check
    if prof is not None:
        _cross_check(v, prof)

    # rung 4: contract
    _contract(v, prof)
    return v


def _cross_check(v: Verdict, prof: dict) -> None:
    a = v.accepted
    if prof["grain"] == "mixed" or a.get("grain") == "mixed":
        v.add("data", BLOCK, f"grain changes inside the file (profile spacing: {prof.get('spacing_days_counts')})")
        return
    if a.get("grain") not in (None, "unknown") and prof["grain"] != a["grain"]:
        v.add("data", BLOCK, f"spec says grain={a['grain']!r} but data is {prof['grain']!r}")
    if prof["grain"] == "weekly":
        wsd, label = a.get("week_start_day"), a.get("date_label")
        if wsd in WEEKDAYS and label in ("period_start", "period_end") and prof["weekday_purity"] > 0.99:
            expected = wsd if label == "period_start" else WEEKDAYS[(WEEKDAYS.index(wsd) - 1) % 7]
            if prof["dominant_weekday"] != expected:
                v.add("data", BLOCK, f"spec implies dates fall on {expected}, data dates fall on "
                                     f"{prof['dominant_weekday']}")
            else:
                v.add("data", PASS, f"dates fall on {expected}, consistent with spec")
        if prof.get("weeks_crossing_month_end", 0) > 0:
            v.add("data", WARN, f"{prof['weeks_crossing_month_end']} weeks cross a month end and must be split")
    if prof["grain"] == "monthly" and not prof["all_first_of_month"]:
        v.add("data", BLOCK, "monthly file has dates that are not the 1st; cannot be a calendar-month key")
    if prof.get("duplicates"):
        v.add("data", BLOCK, f"{prof['duplicates']} duplicate dates")
    if prof.get("missing_periods"):
        v.add("data", WARN, f"{prof['missing_periods']} missing periods")


def _contract(v: Verdict, prof: dict | None) -> None:
    a = v.accepted
    grain = prof["grain"] if prof else a.get("grain")
    cal = a.get("calendar_system", "unknown")
    if grain == "daily":
        v.add("contract", PASS, "daily data sums exactly into calendar months")
        return
    if grain == "monthly":
        if cal == "gregorian":
            v.add("contract", PASS, "calendar months, joins directly")
        else:
            v.add("contract", BLOCK, f"monthly rows on calendar system {cal!r}: a first-of-month date does not "
                                     "prove a calendar month; needs a mapping table before joining")
        return
    if grain == "weekly":
        wsd, label = a.get("week_start_day"), a.get("date_label")
        if wsd in WEEKDAYS and label in ("period_start", "period_end"):
            v.transform = f"apportion_by_day(week_start_day={wsd}, date_label={label})"
            v.add("contract", TRANSFORM, "weekly rows: split each week across its days, then sum by calendar month")
        else:
            v.add("contract", BLOCK, "weekly rows but week start day or date label is unknown; "
                                     "cannot place days in months safely")
        if prof and prof.get("period_columns"):
            v.add("contract", WARN, f"file carries period columns {prof['period_columns']}: never join these "
                                    "to a calendar-month key")
        return
    v.add("contract", BLOCK, f"grain {grain!r} not supported")
