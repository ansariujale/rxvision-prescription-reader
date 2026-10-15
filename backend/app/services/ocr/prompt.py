"""Shared instructions and schema for vision LLM providers."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta

from app.services.ocr.base import ExtractedMedicine, OcrResult, ProviderError

PROMPT = """You are reading a photo of a medical prescription, often handwritten.

Return JSON with these keys:
- "text": every line you can read on the page, top to bottom, separated by \\n.
- "medicines": one object per prescribed medicine, in the order written.
- "doctor": the prescribing doctor's name as printed or written, or null.
- "date": the date the prescription was written, as YYYY-MM-DD, or null.

For each medicine:
- "name": the brand or generic name exactly as written, without the dosage form
  prefix (drop "Tab", "Cap", "Syp", "Inj").
- "strength": e.g. "650 mg", "5 ml", or null.
- "dose": amount per intake, e.g. "1 tablet", "1/2 tablet", "10 ml", or null.
- "frequency": a pattern like "1-0-1" if written that way, otherwise the
  abbreviation or phrase as written ("BD", "TDS", "at night"), or null.
- "duration": e.g. "5 days", "2 weeks", or null.
- "timing": "Before food", "After food", "Empty stomach", "With food", or null.
- "notes": any other instruction for this medicine, or null.
- "source_line": the line on the page this medicine was read from, verbatim.

Rules:
- Only include medicines. Ignore the letterhead, doctor and patient details,
  diagnosis, tests and advice.
- Never guess a name you cannot read. If a word is illegible, copy your best
  reading of the letters rather than substituting a medicine you know.
- Use null for anything not written. Do not infer doses.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "doctor": {"type": "string", "nullable": True},
        "date": {"type": "string", "nullable": True},
        "medicines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "strength": {"type": "string", "nullable": True},
                    "dose": {"type": "string", "nullable": True},
                    "frequency": {"type": "string", "nullable": True},
                    "duration": {"type": "string", "nullable": True},
                    "timing": {"type": "string", "nullable": True},
                    "notes": {"type": "string", "nullable": True},
                    "source_line": {"type": "string", "nullable": True},
                },
                "required": ["name"],
            },
        },
    },
    "required": ["text", "medicines"],
}

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_FIELDS = ("strength", "dose", "frequency", "duration", "timing", "notes", "source_line")


def _clean(value) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value[:300] or None


def parse_response(raw: str) -> OcrResult:
    """Turn the model's JSON into an OcrResult, tolerating code fences."""
    try:
        data = json.loads(_FENCE.sub("", raw.strip()))
    except json.JSONDecodeError as e:
        raise ProviderError("The OCR service returned an unreadable response", str(e))
    if not isinstance(data, dict):
        raise ProviderError("The OCR service returned an unexpected response")

    text = str(data.get("text") or "")
    medicines = []
    for m in data.get("medicines") or []:
        if not isinstance(m, dict):
            continue
        name = _clean(m.get("name"))
        if not name:
            continue
        medicines.append(ExtractedMedicine(name=name, **{f: _clean(m.get(f)) for f in _FIELDS}))

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    doctor = _clean(data.get("doctor"))
    return OcrResult(
        text=text,
        lines=lines,
        medicines=medicines,
        doctor=doctor[:160] if doctor else None,
        prescribed_on=_parse_date(data.get("date")),
    )


def _parse_date(raw) -> date | None:
    """Accept a plausible YYYY-MM-DD; anything else or in the future is dropped."""
    try:
        d = date.fromisoformat(str(raw).strip())
    except (TypeError, ValueError):
        return None
    today = date.today()
    return d if today - timedelta(days=3650) <= d <= today else None
