import json
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, Session
from app.models import Scan, ScanItem, ScanStatus
from app.schemas import MedicineBrief, MedicineUse, MyMedicineOut
from app.services.routine import active_window, course_start

router = APIRouter(prefix="/me", tags=["me"])


async def _done_scans(session, user_id) -> list[Scan]:
    return list(
        (
            await session.execute(
                select(Scan)
                .where(Scan.user_id == user_id, Scan.status == ScanStatus.DONE)
                .options(selectinload(Scan.items).joinedload(ScanItem.medicine))
                .order_by(Scan.created_at.desc())
            )
        ).scalars().unique()
    )


@router.get("/medicines", response_model=list[MyMedicineOut])
async def my_medicines(
    session: Session,
    user: CurrentUser,
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    """Every medicine the user has been prescribed, one row per medicine."""
    today = date.today()
    groups: dict[str, MyMedicineOut] = {}
    needle = (q or "").strip().lower()

    for scan in await _done_scans(session, user.id):
        start = course_start(scan)
        for item in scan.items:
            if needle and needle not in item.name.lower():
                continue
            key = f"m{item.medicine_id}" if item.medicine_id else f"n:{item.name.strip().lower()}"
            use = MedicineUse(
                scan_id=scan.id, scan_title=scan.title, prescribed_on=start, item_id=item.id,
                strength=item.strength, dose=item.dose, frequency=item.frequency,
                duration=item.duration, timing=item.timing, in_routine=scan.in_routine,
            )
            active = scan.in_routine and active_window(scan, item, today) is not None
            group = groups.get(key)
            if group is None:
                groups[key] = MyMedicineOut(
                    key=key,
                    name=item.medicine.name if item.medicine else item.name,
                    medicine=MedicineBrief.model_validate(item.medicine) if item.medicine else None,
                    times=1, last_prescribed=start, active=active, uses=[use],
                )
            else:
                group.times += 1
                group.active = group.active or active
                group.last_prescribed = max(group.last_prescribed, start)
                group.uses.append(use)

    return sorted(groups.values(), key=lambda g: (not g.active, -g.last_prescribed.toordinal(), g.name.lower()))


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


@router.get("/export")
async def export_everything(session: Session, user: CurrentUser):
    scans = await _done_scans(session, user.id)
    payload = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "account": {"email": user.email, "name": user.name, "created_at": user.created_at},
        "prescriptions": [
            {
                "title": s.title, "prescribed_on": course_start(s), "doctor": s.doctor,
                "in_routine": s.in_routine, "provider": s.provider, "raw_text": s.raw_text,
                "items": [
                    {
                        "name": i.name, "catalogue_name": i.medicine.name if i.medicine else None,
                        "strength": i.strength, "dose": i.dose, "frequency": i.frequency,
                        "duration": i.duration, "timing": i.timing, "notes": i.notes,
                        "status": i.status, "confidence": i.confidence, "source_line": i.source_line,
                    }
                    for i in s.items
                ],
            }
            for s in scans
        ],
    }
    return Response(
        json.dumps(payload, indent=2, default=_json_default, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="rxvision-export.json"'},
    )
