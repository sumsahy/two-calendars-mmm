"""Verification ladder for LLM spec readings, and the refresh gate.

    rung 1  SCHEMA     the LLM output parses and uses allowed values               -> else BLOCK
    rung 2  GROUNDING  each quote appears VERBATIM in the spec (after whitespace and
                       markdown normalisation), is long enough to mean something, and
                       actually SUPPORTS the claimed value (deterministic keyword rules) -> else claim discarded
    rung 3  SPEC SCAN  a deterministic scan of the spec text extracts the same facts
                       where it can; any disagreement with the LLM                  -> BLOCK
    rung 4  DATA       claims agree with the deterministic profile of the file      -> else BLOCK
    rung 5  CONTRACT   source can reach Gregorian calendar months safely:
                         aligned, confirmed by BOTH LLM and spec scan -> PASS
                         aligned per LLM only                         -> WARN (human review)
                         known transform                              -> TRANSFORM, re-checked in run.py
                         anything unknown or conflicting              -> BLOCK

Design rule (D-017, tightened after the independent review, R-03):
the LLM can only make the gate stricter. No LLM claim alone can turn a BLOCK into a PASS.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from pydantic import ValidationError

from .llm_spec_reader import SpecReading
from .profiler import WEEKDAYS

PASS, WARN, TRANSFORM, BLOCK = "PASS", "WARN", "TRANSFORM", "BLOCK"
_ORDER = {PASS: 0, WARN: 1, TRANSFORM: 2, BLOCK: 3}
MIN_QUOTE_CHARS = 10  # and at least two words: a lone "Sunday" or "weekly" proves nothing
_DAY = "(" + "|".join(WEEKDAYS) + ")"


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


# ----------------------------------------------------------------- text helpers
def _norm(s: str) -> str:
    s = s.lower()
    for a, b in (("–", "-"), ("—", "-"), ("’", "'"), ("“", '"'), ("”", '"')):
        s = s.replace(a, b)
    s = re.sub(r"[`*_|#>]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def is_grounded(quote: str, spec_text: str) -> bool:
    """Exact (normalised) substring match only. No fuzzy matching: a one-word swap must fail."""
    q = _norm(quote).rstrip(".")
    return len(q) >= MIN_QUOTE_CHARS and len(q.split()) >= 2 and q in _norm(spec_text)


def implied_week_start(text: str) -> str | None:
    """Deterministic: which weekday a week STARTS on, if the text says so unambiguously."""
    t = _norm(text)
    found = set()
    for m in re.finditer(_DAY + r" (?:to|through|-) " + _DAY, t):
        found.add(m.group(1))
    for m in re.finditer(_DAY + r" (?:that )?(?:begins|starts|start)", t):
        found.add(m.group(1))
    for m in re.finditer(r"(?:begins|starts|starting|keyed by|identified by|labelled by) (?:on )?(?:the )?" + _DAY, t):
        if "end" not in t[max(0, m.start() - 25): m.start()]:
            found.add(m.group(1))
    for m in re.finditer(r"(?:end|ends|ending|closes) (?:on )?(?:the )?" + _DAY, t):
        found.add(WEEKDAYS[(WEEKDAYS.index(m.group(1)) + 1) % 7])
    for m in re.finditer(r"week-ending (?:date )?\(?(?:the )?" + _DAY, t):
        found.add(WEEKDAYS[(WEEKDAYS.index(m.group(1)) + 1) % 7])
    for m in re.finditer(r"week-ending " + _DAY, t):
        found.add(WEEKDAYS[(WEEKDAYS.index(m.group(1)) + 1) % 7])
    return found.pop() if len(found) == 1 else ("conflict" if len(found) > 1 else None)


def implied_date_label(text: str) -> str | None:
    t = _norm(text)
    end = bool(re.search(r"week-ending|ends? |ending |closes|week ending", t))
    start = bool(re.search(r"begins|starts|first day|first of the month|keyed by|identified by|labelled by the "
                           + _DAY + r" that starts|week_start|week start", t))
    if end and not start:
        return "period_end"
    if start and not end:
        return "period_start"
    return None


_GRAIN_WORDS = {"weekly": r"week", "monthly": r"month", "daily": r"daily|per (?:calendar )?day|one row per day",
                "mixed": r"switch|from .* onwards|up to"}
_CAL_WORDS = {"gregorian": r"calendar[- ]month|gregorian|calendar day",
              "media_445": r"4-4-5", "broadcast": r"broadcast month", "fiscal_445": r"fiscal"}


def supports(field_name: str, value: str, quote: str) -> bool:
    """Does the quote, read deterministically, support the claimed value?"""
    q = _norm(quote)
    if field_name == "grain":
        return bool(re.search(_GRAIN_WORDS.get(value, r"$^"), q))
    if field_name == "calendar_system":
        ok = bool(re.search(_CAL_WORDS.get(value, r"$^"), q))
        if value == "gregorian":
            ok = ok and not re.search(r"fiscal|broadcast|4-4-5|media", q)
        return ok
    if field_name == "week_start_day":
        return implied_week_start(q) == value
    if field_name == "date_label":
        return implied_date_label(q) == value
    return False


def spec_scan(spec_text: str) -> dict:
    """What a deterministic reader can extract from the WHOLE spec, independent of the LLM."""
    t = _norm(spec_text)
    cal = set()
    if re.search(r"fiscal", t):
        cal.add("fiscal_445")
    if re.search(r"4-4-5", t) and not re.search(r"fiscal", t):
        cal.add("media_445")
    if re.search(r"broadcast month", t):
        cal.add("broadcast")
    if re.search(r"calendar[- ]month|gregorian", t) and not cal:
        cal.add("gregorian")
    return {
        "week_start_day": implied_week_start(spec_text),
        "calendar_system": cal.pop() if len(cal) == 1 else ("conflict" if cal else None),
        "injection": bool(re.search(r"ignore (?:all )?(?:previous|prior) instructions|automated readers?|"
                                    r"note to (?:the )?(?:ai|llm|model)", t)),
    }


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

    # rung 2: grounding (verbatim + supports the value)
    for name in ("grain", "calendar_system", "week_start_day", "date_label"):
        claim = getattr(reading.fields, name)
        if claim.value in ("unknown", "not_applicable"):
            v.accepted[name] = claim.value
            continue
        if not is_grounded(claim.evidence, spec_text):
            v.accepted[name] = "unknown"
            v.add("grounding", WARN, f"{name}={claim.value!r} discarded: quote not found verbatim in spec "
                                     f"({claim.evidence[:60]!r})")
        elif not supports(name, claim.value, claim.evidence):
            v.accepted[name] = "unknown"
            v.add("grounding", WARN, f"{name}={claim.value!r} discarded: the quote does not support that value "
                                     f"({claim.evidence[:60]!r})")
        else:
            v.accepted[name] = claim.value

    # rung 3: deterministic spec scan, independent of the LLM
    scan = spec_scan(spec_text)
    v.accepted["_spec_scan"] = scan
    if scan["injection"]:
        v.add("spec_scan", WARN, "spec contains text addressed to automated readers; it was not followed")
    for f in ("week_start_day", "calendar_system"):
        s, a = scan[f], v.accepted.get(f)
        if s == "conflict":
            v.add("spec_scan", BLOCK, f"spec text gives conflicting {f}; needs a human")
        elif s and a not in (None, "unknown", "not_applicable") and s != a:
            v.add("spec_scan", BLOCK, f"LLM says {f}={a!r} but the spec text says {s!r}")

    # rung 4: data cross-check
    if prof is not None:
        _cross_check(v, prof)

    # rung 5: contract
    _contract(v, prof, scan)
    return v


def _cross_check(v: Verdict, prof: dict) -> None:
    a = v.accepted
    if prof.get("bad_values"):
        v.add("data", BLOCK, f"invalid values: {prof['bad_values']}")
    if prof["grain"] == "mixed" or a.get("grain") == "mixed":
        v.add("data", BLOCK, f"grain changes inside the file (profile spacing: {prof.get('spacing_days_counts')})")
        return
    if prof["grain"] == "unknown":
        v.add("data", BLOCK, f"irregular date spacing {prof.get('spacing_days_counts')}")
        return
    if a.get("grain") not in (None, "unknown") and prof["grain"] != a["grain"]:
        v.add("data", BLOCK, f"spec says grain={a['grain']!r} but data is {prof['grain']!r}")
    if prof["grain"] == "weekly":
        if prof["weekday_purity"] < 1.0:
            v.add("data", BLOCK, f"dates fall on more than one weekday (purity {prof['weekday_purity']:.1%})")
        wsd, label = a.get("week_start_day"), a.get("date_label")
        if wsd in WEEKDAYS and label in ("period_start", "period_end"):
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
        v.add("data", BLOCK, f"{prof['missing_periods']} missing periods (gaps in the series)")


def _contract(v: Verdict, prof: dict | None, scan: dict) -> None:
    a = v.accepted
    grain = prof["grain"] if prof else a.get("grain")
    cal = a.get("calendar_system", "unknown")
    if grain == "daily":
        v.add("contract", PASS, "daily data sums exactly into calendar months")
        return
    if grain == "monthly":
        if cal == "gregorian" and scan["calendar_system"] == "gregorian":
            v.add("contract", PASS, "calendar months (LLM and spec scan agree), joins directly")
        elif cal == "gregorian":
            v.add("contract", WARN, "LLM says calendar months but the spec scan cannot confirm it: human review")
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
