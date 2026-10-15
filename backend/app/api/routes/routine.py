from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, Session
from app.core.errors import ApiError
from app.models import DoseLog, Scan, ScanItem, ScanStatus, User
from app.schemas import DayCount, DoseIn, RoutineEntryOut, RoutineOut, RoutineSlotOut
from app.services.routine import Entry, plan_day

router = APIRouter(prefix="/routine", tags=["routine"])


async def routine_scans(session, user: User) -> list[Scan]:
    return list(
        (
            await session.execute(
                select(Scan)
                .where(Scan.user_id == user.id, Scan.in_routine.is_(True), Scan.status == ScanStatus.DONE)
                .options(selectinload(Scan.items))
            )
        ).scalars()
    )


async def taken_on(session, user: User, start: date, end: date) -> dict[date, set[tuple[str, str]]]:
    rows = await session.execute(
        select(DoseLog.item_id, DoseLog.day, DoseLog.slot)
        .join(ScanItem, ScanItem.id == DoseLog.item_id)
        .join(Scan, Scan.id == ScanItem.scan_id)
        .where(Scan.user_id == user.id, DoseLog.day >= start, DoseLog.day <= end)
    )
    out: dict[date, set[tuple[str, str]]] = {}
    for item_id, day, slot in rows:
        out.setdefault(day, set()).add((str(item_id), slot))
    return out


def entry_out(e: Entry) -> RoutineEntryOut:
    i = e.item
    return RoutineEntryOut(
        item_id=i.id, scan_id=e.scan.id, scan_title=e.scan.title, name=i.name,
        medicine_id=i.medicine_id, strength=i.strength, dose=i.dose, frequency=i.frequency,
        timing=i.timing, notes=i.notes, slot=e.slot, quantity=e.quantity, taken=e.taken,
        day_of_course=e.day_of_course, total_days=e.total_days, ends_on=e.ends_on, flags=e.flags,
    )


@router.get("", response_model=RoutineOut)
async def get_routine(
    session: Session,
    user: CurrentUser,
    day: Annotated[date | None, Query()] = None,
):
    # The client sends its local date; the server's clock may be in another zone.
    day = day or date.today()
    week_start = day - timedelta(days=day.weekday())
    week = [week_start + timedelta(days=n) for n in range(7)]

    scans = await routine_scans(session, user)
    logs = await taken_on(session, user, week[0], week[-1])

    plan = plan_day(scans, day, logs.get(day, set()))
    counts = []
    for d in week:
        scheduled = plan_day(scans, d, logs.get(d, set())).scheduled
        counts.append(DayCount(day=d, total=len(scheduled), taken=sum(e.taken for e in scheduled)))

    scheduled = plan.scheduled
    return RoutineOut(
        day=day,
        slots=[
            RoutineSlotOut(slot=slot, entries=[entry_out(e) for e in entries])
            for slot, entries in plan.slots.items()
            if entries
        ],
        as_needed=[entry_out(e) for e in plan.as_needed],
        ending_soon=[entry_out(e) for e in plan.ending_soon],
        taken=sum(e.taken for e in scheduled),
        total=len(scheduled),
        week=counts,
        prescriptions=len(scans),
    )


@router.put("/doses", status_code=204)
async def set_dose(body: DoseIn, session: Session, user: CurrentUser):
    owned = await session.scalar(
        select(ScanItem.id)
        .join(Scan, Scan.id == ScanItem.scan_id)
        .where(ScanItem.id == body.item_id, Scan.user_id == user.id)
    )
    if owned is None:
        raise ApiError(404, "Item not found")
    if body.day > date.today() + timedelta(days=1):
        raise ApiError(422, "You cannot mark a future dose as taken")

    where = (DoseLog.item_id == body.item_id, DoseLog.day == body.day, DoseLog.slot == body.slot)
    if body.taken:
        exists = await session.scalar(select(DoseLog.id).where(*where))
        if exists is None:
            session.add(DoseLog(item_id=body.item_id, day=body.day, slot=body.slot))
            try:
                await session.commit()
            except IntegrityError:  # a double tap raced itself; the row exists
                await session.rollback()
    else:
        await session.execute(delete(DoseLog).where(*where))
        await session.commit()
