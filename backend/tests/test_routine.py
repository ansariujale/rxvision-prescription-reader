import doctest
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.models import Scan, ScanItem
from app.services import routine
from app.services.routine import duration_days, plan_day, slots_for

START = date(2026, 10, 10)


def test_doctests():
    assert doctest.testmod(routine).failed == 0


@pytest.mark.parametrize(
    "frequency, timing, expected",
    [
        ("1-0-1", None, [("morning", "1"), ("night", "1")]),
        ("1-1-1", None, [("morning", "1"), ("afternoon", "1"), ("night", "1")]),
        ("1/2-0-1/2", None, [("morning", "1/2"), ("night", "1/2")]),
        ("0-0-1", None, [("night", "1")]),
        ("1-0-0-1", None, [("morning", "1"), ("night", "1")]),
        ("0-1-1-0", None, [("afternoon", "1"), ("evening", "1")]),
        ("Three times daily", None, [("morning", None), ("afternoon", None), ("night", None)]),
        ("Four times daily", None, [("morning", None), ("afternoon", None), ("evening", None), ("night", None)]),
        ("At bedtime", None, [("night", None)]),
        ("As needed", None, [("as_needed", None)]),
        ("Once daily", "At bedtime", [("night", None)]),
        (None, None, [("morning", None)]),
    ],
)
def test_slots_for(frequency, timing, expected):
    assert slots_for(frequency, timing) == expected


@pytest.mark.parametrize(
    "text, days", [("5 days", 5), ("1 week", 7), ("2 weeks", 14), ("1 month", 30), ("for 10 Days", 10), (None, None), ("SOS", None)]
)
def test_duration_days(text, days):
    assert duration_days(text) == days


def make_scan(*items: dict, prescribed_on=START) -> Scan:
    scan = Scan(
        id=uuid.uuid4(), title="Rx", prescribed_on=prescribed_on,
        created_at=datetime(2026, 10, 10, tzinfo=UTC), in_routine=True,
    )
    scan.items = [ScanItem(id=uuid.uuid4(), name=i.pop("name"), **i) for i in items]
    return scan


def test_course_window_and_day_numbers():
    scan = make_scan({"name": "Augmentin", "frequency": "1-0-1", "duration": "5 days"})
    assert plan_day([scan], START - timedelta(days=1), set()).scheduled == []
    first = plan_day([scan], START, set())
    assert [e.slot for e in first.scheduled] == ["morning", "night"]
    assert first.scheduled[0].day_of_course == 1 and first.scheduled[0].total_days == 5
    last = plan_day([scan], START + timedelta(days=4), set())
    assert last.scheduled[0].day_of_course == 5
    assert len(last.ending_soon) == 1
    assert plan_day([scan], START + timedelta(days=5), set()).scheduled == []


def test_missing_duration_and_unknown_frequency_are_flagged():
    scan = make_scan({"name": "Mystery", "frequency": "every other day"})
    entry = plan_day([scan], START, set()).scheduled[0]
    assert entry.total_days == 30
    assert set(entry.flags) == {"no_duration", "check_frequency"}


def test_weekly_only_on_course_days_1_8_15():
    scan = make_scan({"name": "D-Rise", "frequency": "Once weekly", "duration": "1 month"})
    days = [n for n in range(30) if plan_day([scan], START + timedelta(days=n), set()).scheduled]
    assert days == [0, 7, 14, 21, 28]


def test_taken_and_as_needed():
    scan = make_scan(
        {"name": "Pan", "frequency": "1-0-0", "duration": "7 days"},
        {"name": "Dolo", "frequency": "As needed", "duration": "3 days"},
    )
    pan = scan.items[0]
    plan = plan_day([scan], START, {(str(pan.id), "morning")})
    assert plan.scheduled[0].taken is True
    assert [e.item.name for e in plan.as_needed] == ["Dolo"]
