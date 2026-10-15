"""Turn prescriptions into a daily routine.

Nothing here is stored. The routine for a day is derived from the items of
prescriptions marked `in_routine`, so editing an item's frequency or duration
changes the routine immediately. Only the user's ticks (dose logs) persist.

    >>> slots_for("1-0-1", None)
    [('morning', '1'), ('night', '1')]
    >>> slots_for("Twice daily", None)
    [('morning', None), ('night', None)]
    >>> duration_days("2 weeks")
    14
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.models import Scan, ScanItem, Slot

DEFAULT_COURSE_DAYS = 30
ENDING_SOON_DAYS = 2

_PATTERN = re.compile(r"^\s*([\d/½.]+)(?:\s*-\s*([\d/½.]+)){2,3}\s*$")
_PART = re.compile(r"[\d/½.]+")
_DURATION = re.compile(r"(\d{1,3})\s*(day|week|month)", re.IGNORECASE)
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30}

_WORDS: list[tuple[str, tuple[str, ...]]] = [
    ("four times", (Slot.MORNING, Slot.AFTERNOON, Slot.EVENING, Slot.NIGHT)),
    ("three times", (Slot.MORNING, Slot.AFTERNOON, Slot.NIGHT)),
    ("twice", (Slot.MORNING, Slot.NIGHT)),
    ("bedtime", (Slot.NIGHT,)),
    ("night", (Slot.NIGHT,)),
    ("as needed", (Slot.AS_NEEDED,)),
    ("immediately", (Slot.MORNING,)),
    ("once weekly", (Slot.MORNING,)),
    ("once daily", (Slot.MORNING,)),
]

ORDER = {s: i for i, s in enumerate(Slot.ALL)}


def _is_zero(part: str) -> bool:
    return part in ("0", "0.0")


def slots_for(frequency: str | None, timing: str | None) -> list[tuple[str, str | None]]:
    """(slot, quantity) pairs for one item. Quantity only comes from patterns."""
    freq = (frequency or "").strip()
    if _PATTERN.match(freq):
        parts = _PART.findall(freq)
        names = (
            (Slot.MORNING, Slot.AFTERNOON, Slot.NIGHT)
            if len(parts) == 3
            else (Slot.MORNING, Slot.AFTERNOON, Slot.EVENING, Slot.NIGHT)
        )
        return [(n, p.replace("½", "1/2")) for n, p in zip(names, parts) if not _is_zero(p)]

    lowered = freq.lower()
    slots: tuple[str, ...] = (Slot.MORNING,)
    for word, mapped in _WORDS:
        if word in lowered:
            slots = mapped
            break
    if slots == (Slot.MORNING,) and timing and "bedtime" in timing.lower():
        slots = (Slot.NIGHT,)
    return [(s, None) for s in slots]


def understood(frequency: str | None) -> bool:
    freq = (frequency or "").strip().lower()
    return bool(freq) and (bool(_PATTERN.match(freq)) or any(w in freq for w, _ in _WORDS))


def duration_days(duration: str | None) -> int | None:
    if not duration:
        return None
    m = _DURATION.search(duration)
    if not m:
        return None
    return int(m.group(1)) * _UNIT_DAYS[m.group(2).lower()]


def course_start(scan: Scan) -> date:
    return scan.prescribed_on or scan.created_at.date()


@dataclass
class Entry:
    item: ScanItem
    scan: Scan
    slot: str
    quantity: str | None
    taken: bool
    day_of_course: int
    total_days: int
    ends_on: date
    flags: list[str] = field(default_factory=list)


@dataclass
class DayPlan:
    day: date
    slots: dict[str, list[Entry]]
    as_needed: list[Entry]
    ending_soon: list[Entry]

    @property
    def scheduled(self) -> list[Entry]:
        return [e for entries in self.slots.values() for e in entries]


def active_window(scan: Scan, item: ScanItem, day: date) -> tuple[int, int, date, list[str]] | None:
    """(day_of_course, total_days, ends_on, flags) if the item runs on `day`."""
    flags: list[str] = []
    total = duration_days(item.duration)
    if total is None:
        total = DEFAULT_COURSE_DAYS
        flags.append("no_duration")
    if not understood(item.frequency):
        flags.append("check_frequency")
    start = course_start(scan)
    offset = (day - start).days
    if offset < 0 or offset >= total:
        return None
    if item.frequency and "weekly" in item.frequency.lower() and offset % 7 != 0:
        return None
    return offset + 1, total, start + timedelta(days=total - 1), flags


def plan_day(scans: list[Scan], day: date, taken: set[tuple[str, str]]) -> DayPlan:
    """Build the plan for one day. `taken` holds (item_id, slot) pairs."""
    slots: dict[str, list[Entry]] = {s: [] for s in Slot.ALL if s != Slot.AS_NEEDED}
    as_needed: list[Entry] = []
    ending: dict[str, Entry] = {}

    for scan in scans:
        for item in scan.items:
            window = active_window(scan, item, day)
            if window is None:
                continue
            day_of_course, total, ends_on, flags = window
            for slot, quantity in slots_for(item.frequency, item.timing):
                entry = Entry(
                    item=item, scan=scan, slot=slot, quantity=quantity,
                    taken=(str(item.id), slot) in taken,
                    day_of_course=day_of_course, total_days=total, ends_on=ends_on, flags=flags,
                )
                (as_needed if slot == Slot.AS_NEEDED else slots[slot]).append(entry)
                if "no_duration" not in flags and (ends_on - day).days < ENDING_SOON_DAYS:
                    ending.setdefault(str(item.id), entry)

    for entries in slots.values():
        entries.sort(key=lambda e: e.item.name.lower())
    return DayPlan(day=day, slots=slots, as_needed=as_needed, ending_soon=list(ending.values()))


def scheduled_count(scans: list[Scan], day: date) -> int:
    """How many scheduled doses fall on a day (for the week strip)."""
    return len(plan_day(scans, day, set()).scheduled)
