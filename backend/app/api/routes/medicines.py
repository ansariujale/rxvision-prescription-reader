import re
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, Session
from app.core.errors import ApiError
from app.models import Medicine, Scan, ScanItem, ScanStatus
from app.schemas import AlternativeOut, MedicineHit, MedicineOut, MedicineUse
from app.services.matching.catalog import get_index
from app.services.routine import course_start

router = APIRouter(prefix="/medicines", tags=["medicines"])

MAX_ALTERNATIVES = 12
_WS = re.compile(r"\s+")
_UNIT = re.compile(r"(\d)\s+(mg|mcg|ml|g|iu|%)", re.IGNORECASE)


def normalise_composition(text: str | None) -> str:
    """Same molecules and strengths compare equal regardless of spacing or order."""
    if not text:
        return ""
    text = _UNIT.sub(r"\1\2", _WS.sub(" ", text.lower())).strip()
    return " + ".join(sorted(p.strip() for p in text.split("+") if p.strip()))


async def _get(session, medicine_id: int) -> Medicine:
    medicine = await session.get(Medicine, medicine_id)
    if medicine is None:
        raise ApiError(404, "Medicine not found")
    return medicine


@router.get("/search", response_model=list[MedicineHit])
async def search(
    _: CurrentUser,
    q: Annotated[str, Query(min_length=1, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
):
    return [
        MedicineHit(id=m.medicine_id, name=m.name, score=round(m.score, 1))
        for m in get_index().search(q, limit)
    ]


@router.get("/{medicine_id}", response_model=MedicineOut)
async def get_medicine(medicine_id: int, session: Session, _: CurrentUser):
    return await _get(session, medicine_id)


@router.get("/{medicine_id}/alternatives", response_model=list[AlternativeOut])
async def alternatives(medicine_id: int, session: Session, _: CurrentUser):
    """Catalogue products with an identical composition, cheapest first.

    Exact match on the normalised composition only: anything fuzzier risks
    suggesting a different drug or strength.
    """
    medicine = await _get(session, medicine_id)
    target = normalise_composition(medicine.composition)
    if not target:
        return []
    # Narrow in SQL by the first ingredient, then compare exactly in Python.
    first = target.split(" + ")[0].split("(")[0].strip()
    rows = (
        await session.execute(
            select(Medicine)
            .where(Medicine.id != medicine.id, func.lower(Medicine.composition).like(f"%{first}%"))
            .limit(2000)
        )
    ).scalars()
    same = [m for m in rows if normalise_composition(m.composition) == target]
    same.sort(key=lambda m: (m.price is None, m.price or 0, m.name.lower()))
    seen, out = set(), []
    for m in same:
        if m.name.lower() in seen:
            continue
        seen.add(m.name.lower())
        out.append(m)
    return out[:MAX_ALTERNATIVES]


@router.get("/{medicine_id}/history", response_model=list[MedicineUse])
async def history(medicine_id: int, session: Session, user: CurrentUser):
    """Where this medicine appears in the user's own prescriptions."""
    await _get(session, medicine_id)
    rows = (
        await session.execute(
            select(ScanItem, Scan)
            .join(Scan, Scan.id == ScanItem.scan_id)
            .where(
                ScanItem.medicine_id == medicine_id,
                Scan.user_id == user.id,
                Scan.status == ScanStatus.DONE,
            )
            .order_by(Scan.created_at.desc())
        )
    ).all()
    return [
        MedicineUse(
            scan_id=scan.id, scan_title=scan.title, prescribed_on=course_start(scan), item_id=item.id,
            strength=item.strength, dose=item.dose, frequency=item.frequency,
            duration=item.duration, timing=item.timing, in_routine=scan.in_routine,
        )
        for item, scan in rows
    ]
