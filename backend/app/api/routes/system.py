from fastapi import APIRouter
from sqlalchemy import func, select, text

from app.api.deps import CurrentUser, Session
from app.models import ItemStatus, Scan, ScanItem
from app.schemas import ProvidersOut, StatsOut
from app.services.matching.catalog import get_index
from app.services.ocr.factory import active_name, configured

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(session: Session):
    try:
        await session.execute(text("select 1"))
        db = "ok"
    except Exception:
        db = "unavailable"
    return {"status": "ok" if db == "ok" else "degraded", "database": db, "catalogue": len(get_index())}


@router.get("/providers", response_model=ProvidersOut)
async def providers():
    return ProvidersOut(active=active_name(), configured=configured())


@router.get("/stats", response_model=StatsOut)
async def stats(session: Session, user: CurrentUser):
    scans = await session.scalar(select(func.count()).where(Scan.user_id == user.id))
    rows = (
        await session.execute(
            select(ScanItem.status, ScanItem.confidence)
            .join(Scan, Scan.id == ScanItem.scan_id)
            .where(Scan.user_id == user.id)
        )
    ).all()
    confirmed = sum(1 for s, _ in rows if s in (ItemStatus.CONFIRMED, ItemStatus.EDITED, ItemStatus.MANUAL))
    review = sum(1 for s, c in rows if s == ItemStatus.SUGGESTED and (c is None or c < 0.85))
    return StatsOut(
        scans=scans or 0,
        medicines_found=len(rows),
        confirmed=confirmed,
        needs_review=review,
        catalogue_size=len(get_index()),
    )
