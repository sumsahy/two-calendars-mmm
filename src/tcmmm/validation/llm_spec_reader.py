"""LLM vendor-spec reader. ADVISORY ONLY: its output is verified before anyone acts on it.

Modes
  * live:     calls Groq's OpenAI-compatible chat API (needs GROQ_API_KEY).
  * recorded: loads a saved response from specs/llm_fixtures/<spec_stem>.json.
              Fixtures carry provenance metadata so nobody mistakes them for live output.

Mode is chosen by LLM_MODE (live | recorded). Default: live if GROQ_API_KEY is set, else recorded.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Literal, Optional

import httpx
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = ROOT / "prompts" / "spec_reader.md"
FIXTURE_DIR = Path(os.getenv("LLM_FIXTURE_DIR", ROOT / "specs" / "llm_fixtures"))
LIVE_RECORD_DIR = ROOT / "specs" / "llm_fixtures_groq"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

Grain = Literal["daily", "weekly", "monthly", "mixed", "unknown"]
CalSys = Literal["gregorian", "media_445", "broadcast", "fiscal_445", "unknown"]
WeekDay = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                  "not_applicable", "unknown"]
DateLabel = Literal["period_start", "period_end", "not_applicable", "unknown"]


class Claim(BaseModel):
    value: str
    evidence: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class Fields(BaseModel):
    grain: Claim
    calendar_system: Claim
    week_start_day: Claim
    date_label: Claim


class Risk(BaseModel):
    issue: str
    evidence: str = ""


class SpecReading(BaseModel):
    source_name: str
    fields: Fields
    aligned_to_calendar_month: Optional[bool] = None
    risks: list[Risk] = []

    def validate_enums(self) -> list[str]:
        """Return a list of enum violations (pydantic Literal on nested values kept loose on purpose)."""
        allowed = {
            "grain": Grain.__args__, "calendar_system": CalSys.__args__,
            "week_start_day": WeekDay.__args__, "date_label": DateLabel.__args__,
        }
        errs = []
        for f, ok in allowed.items():
            v = getattr(self.fields, f).value
            if v not in ok:
                errs.append(f"{f}={v!r} not in {ok}")
        return errs


def prompt_for(spec_text: str) -> str:
    return PROMPT_PATH.read_text().replace("{spec_text}", spec_text)


def prompt_sha() -> str:
    return hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()[:12]


def mode() -> str:
    m = os.getenv("LLM_MODE")
    if m:
        return m
    return "live" if os.getenv("GROQ_API_KEY") else "recorded"


def read_spec_live(spec_text: str, model: str | None = None, timeout=60) -> dict:
    key = os.environ["GROQ_API_KEY"]
    model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    r = httpx.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt_for(spec_text)}],
        },
        timeout=timeout,
    )
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    out = json.loads(content)
    out["_provenance"] = {"mode": "live", "provider": "groq", "model": model, "prompt_sha": prompt_sha()}
    return out


def read_spec_recorded(spec_path: Path) -> dict:
    fx = FIXTURE_DIR / f"{Path(spec_path).stem}.json"
    if not fx.exists():
        raise FileNotFoundError(f"no recorded LLM response for {spec_path} (expected {fx})")
    return json.loads(fx.read_text())


def read_spec(spec_path: str | Path) -> tuple[dict, str]:
    """Returns (raw JSON dict, mode used). Parsing and verification happen in verify.py."""
    spec_path = Path(spec_path)
    if mode() == "live":
        return read_spec_live(spec_path.read_text()), "live"
    return read_spec_recorded(spec_path), "recorded"


def record_live(spec_paths: list[Path]) -> None:
    """Run live against Groq and save to specs/llm_fixtures_groq/ (kept separate from the
    Claude-recorded fixtures so the two readers can be compared side by side)."""
    LIVE_RECORD_DIR.mkdir(parents=True, exist_ok=True)
    for p in spec_paths:
        out = read_spec_live(Path(p).read_text())
        (LIVE_RECORD_DIR / f"{Path(p).stem}.json").write_text(json.dumps(out, indent=2))
