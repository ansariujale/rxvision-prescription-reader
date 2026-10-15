"""Rule based dosage parsing for one prescription line.

Used for providers that only return text (Textract, Mock), and to normalise the
fields structured providers return. Each rule removes the span it recognised so
that what remains, `name_part`, is as close to a bare medicine name as possible
before it reaches the matcher.

    >>> p = parse_line("1. Tab Augmentin 625mg 1-0-1 x 5 days after food")
    >>> (p.name_part, p.strength, p.frequency, p.duration, p.timing)
    ('Augmentin', '625 mg', '1-0-1', '5 days', 'After food')
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_I = re.IGNORECASE


@dataclass
class ParsedLine:
    source: str
    name_part: str
    strength: str | None = None
    dose: str | None = None
    frequency: str | None = None
    duration: str | None = None
    timing: str | None = None


# Order matters: longer phrases first so "twice daily" wins over "daily".
_FREQUENCY_WORDS: list[tuple[str, str]] = [
    (r"once\s+(?:a\s+|every\s+)?week|\bweekly\b", "Once weekly"),
    (r"once\s+(?:a\s+)?(?:daily|day)|\bonce\b|\b(?:od|qd|q\.d\.)\b", "Once daily"),
    (r"twice\s+(?:a\s+)?(?:daily|day)|\b(?:bd|bid|b\.d\.|b\.i\.d\.)\b", "Twice daily"),
    (r"thrice\s+(?:a\s+)?(?:daily|day)|three\s+times\s+(?:a\s+)?day|\b(?:tds|tid|t\.d\.s\.)\b",
     "Three times daily"),
    (r"four\s+times\s+(?:a\s+)?day|\b(?:qid|qds|q\.i\.d\.)\b", "Four times daily"),
    (r"at\s+bed\s*time|at\s+night|\bhs\b|\bh\.s\.\b", "At bedtime"),
    (r"as\s+needed|when\s+required|\b(?:sos|prn)\b", "As needed"),
    (r"\bstat\b", "Immediately"),
]
_FREQUENCY_RES = [(re.compile(p, _I), label) for p, label in _FREQUENCY_WORDS]

# 1-0-1, 1-1-1, 0-0-1, 1/2-0-1/2, 1 - 0 - 1
_FRACTION = r"(?:\d/\d|½|\d)"
_PATTERN_RE = re.compile(rf"(?<![\w/]){_FRACTION}\s*-\s*{_FRACTION}\s*-\s*{_FRACTION}(?:\s*-\s*{_FRACTION})?(?![\w/])")

_DURATION_UNITS = {
    "d": "day", "day": "day", "days": "day",
    "w": "week", "wk": "week", "wks": "week", "week": "week", "weeks": "week",
    "m": "month", "mo": "month", "month": "month", "months": "month",
}
# "x 5 days", "for 1 week", "x2w", "5d", "10 days". A bare number + unit needs a
# word unit or a leading x/for, so "5 m" in a name does not become 5 months.
_DURATION_RE = re.compile(
    r"(?:(?:\bx|×|\bfor)\s*(\d{1,3})\s*(days?|d|weeks?|wks?|wk|w|months?|mo|m)\b"
    r"|\b(\d{1,3})\s*(days?|weeks?|months?)\b"
    r"|\b(\d{1,3})(d|w)\b)",
    _I,
)

_TIMING: list[tuple[str, str]] = [
    (r"before\s+(?:food|meals?|breakfast|lunch|dinner)|\bac\b|\ba\.c\.", "Before food"),
    (r"after\s+(?:food|meals?|breakfast|lunch|dinner)|\bpc\b|\bp\.c\.", "After food"),
    (r"(?:on\s+)?empty\s+stomach", "Empty stomach"),
    (r"with\s+(?:food|meals?|milk)", "With food"),
    # Reached only when a 1-0-1 style pattern already set the frequency.
    (r"at\s+bed\s*time|at\s+night|\bhs\b|\bh\.s\.", "At bedtime"),
]
_TIMING_RES = [(re.compile(p, _I), label) for p, label in _TIMING]

_DOSE_UNITS = {
    "tab": "tablet", "tabs": "tablet", "tablet": "tablet", "tablets": "tablet",
    "cap": "capsule", "caps": "capsule", "capsule": "capsule", "capsules": "capsule",
    "puff": "puff", "puffs": "puff", "drop": "drop", "drops": "drop",
    "tsp": "teaspoon", "teaspoon": "teaspoon", "sachet": "sachet", "sachets": "sachet",
}
_DOSE_RE = re.compile(
    r"(?<![\w/])(\d/\d|½|\d+(?:\.\d+)?)\s*(tabs?|tablets?|caps?|capsules?|puffs?|drops?|tsp|teaspoons?|sachets?)\b",
    _I,
)

# 650 mg, 500mg, 0.5 mg, 5 ml, 1 g, 2%, 60k (vitamin D), 40 IU
_STRENGTH_RE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*(mg|mcg|µg|ug|gm|g|ml|iu|%)(?![a-z])|(?<![\w.])(\d{2,3})\s*k\b",
    _I,
)

# Leading list markers and dosage-form prefixes: "1.", "2)", "Tab.", "Cap", "Syp"
_PREFIX_RE = re.compile(
    r"^(?:[^a-z0-9½]+|\d{1,2}\s*[.)\-:]\s*|(?:tabs?|tablet|caps?|capsule|inj|syp|syr|susp|sol|oint|cr|gel|drops?)\b\.?\s*|[a-z]\s*[.\-]\s+)+",
    _I,
)
_WS = re.compile(r"\s+")


def _take(pattern: re.Pattern, text: str) -> tuple[re.Match | None, str]:
    m = pattern.search(text)
    if not m:
        return None, text
    return m, f"{text[: m.start()]} {text[m.end():]}"


def normalise_frequency(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    m = _PATTERN_RE.fullmatch(value)
    if m:
        return re.sub(r"\s*", "", value).replace("½", "1/2")
    for regex, label in _FREQUENCY_RES:
        if regex.search(value):
            return label
    return value[:60]


def _unit_plural(n: str, unit: str) -> str:
    return f"{n} {unit}" if n == "1" else f"{n} {unit}s"


def parse_line(line: str) -> ParsedLine:
    work = line.strip()
    result = ParsedLine(source=line.strip(), name_part="")

    m, work = _take(_PATTERN_RE, work)
    if m:
        result.frequency = re.sub(r"\s*", "", m.group(0)).replace("½", "1/2")
    else:
        for regex, label in _FREQUENCY_RES:
            m, work = _take(regex, work)
            if m:
                result.frequency = label
                break

    m, work = _take(_DURATION_RE, work)
    if m:
        n = m.group(1) or m.group(3) or m.group(5)
        raw_unit = (m.group(2) or m.group(4) or m.group(6)).lower()
        result.duration = _unit_plural(n, _DURATION_UNITS.get(raw_unit, raw_unit))

    for regex, label in _TIMING_RES:
        m, work = _take(regex, work)
        if m:
            result.timing = label
            break

    m, work = _take(_DOSE_RE, work)
    if m:
        amount = m.group(1).replace("1/2", "½")
        unit = _DOSE_UNITS[m.group(2).lower()]
        result.dose = f"{amount} {unit}" if amount in ("1", "½") else f"{amount} {unit}s"

    m = _STRENGTH_RE.search(work)
    if m:
        if m.group(3):
            result.strength = f"{int(m.group(3)) * 1000} IU"
        else:
            unit = m.group(2).lower()
            unit = {"gm": "g", "ug": "mcg", "µg": "mcg", "iu": "IU"}.get(unit, unit)
            result.strength = f"{m.group(1)}%" if unit == "%" else f"{m.group(1)} {unit}"
        work = f"{work[: m.start()]} {work[m.end():]}"

    name = _PREFIX_RE.sub("", _WS.sub(" ", work).strip())
    result.name_part = name.strip(" -,.;:")
    return result
