import json
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, OwnedScan, Session
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.ratelimit import upload_bucket
from app.models import Scan, ScanItem, ScanStatus
from app.schemas import CropIn, Page, ScanAccepted, ScanOut, ScanSummary, ScanUpdate
from app.services import export
from app.services.images import Crop, normalise
from app.services.ocr.factory import active_name
from app.services.pipeline import process_scan
from app.services.storage import get_storage

router = APIRouter(prefix="/scans", tags=["scans"])

CHUNK = 1024 * 1024


def scan_out(scan: Scan) -> ScanOut:
    return ScanOut.model_validate(
        {
            **{c: getattr(scan, c) for c in (
                "id", "title", "status", "provider", "created_at", "completed_at",
                "duration_ms", "error", "raw_text", "image_width", "image_height",
                "prescribed_on", "doctor", "in_routine",
            )},
            "image_url": f"/api/v1/scans/{scan.id}/image",
            "items": scan.items,
        }
    )


def default_title(now: datetime) -> str:
    return f"Prescription, {now.day} {now:%b}"


async def _read_limited(upload: UploadFile, limit_mb: int) -> bytes:
    limit = limit_mb * CHUNK
    buf = bytearray()
    while chunk := await upload.read(CHUNK):
        buf += chunk
        if len(buf) > limit:
            raise ApiError(413, f"Images must be under {limit_mb} MB")
    if not buf:
        raise ApiError(422, "The uploaded file is empty")
    return bytes(buf)


def _parse_crop(raw: str | None) -> Crop | None:
    if not raw:
        return None
    try:
        c = CropIn.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError):
        raise ApiError(422, "crop must be JSON with x, y, width, height between 0 and 1")
    return Crop(c.x, c.y, c.width, c.height)


@router.post("", status_code=202, response_model=ScanAccepted)
async def create_scan(
    request: Request,
    background: BackgroundTasks,
    session: Session,
    user: CurrentUser,
    image: Annotated[UploadFile, File()],
    crop: Annotated[str | None, Form()] = None,
):
    settings = get_settings()
    if settings.rate_limit_enabled and not upload_bucket.allow(f"upload:{user.id}"):
        raise ApiError(429, "You are uploading quickly. Wait a minute and try again.")

    raw = await _read_limited(image, settings.max_upload_mb)
    normalised = normalise(raw, _parse_crop(crop))
    key = get_storage().put(normalised.data)

    now = datetime.now()
    scan = Scan(
        user_id=user.id,
        title=default_title(now),
        status=ScanStatus.QUEUED,
        provider=active_name(),
        image_key=key,
        image_width=normalised.width,
        image_height=normalised.height,
        prescribed_on=now.date(),
    )
    session.add(scan)
    await session.commit()

    background.add_task(process_scan, scan.id)
    return ScanAccepted(id=scan.id, status=scan.status)


def _history_query(user_id: uuid.UUID, q: str | None, in_routine: bool | None = None) -> Select:
    stmt = select(Scan).where(Scan.user_id == user_id)
    if in_routine is not None:
        stmt = stmt.where(Scan.in_routine == in_routine)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Scan.title).like(like),
                func.lower(Scan.doctor).like(like),
                exists().where(ScanItem.scan_id == Scan.id, func.lower(ScanItem.name).like(like)),
            )
        )
    return stmt


@router.get("", response_model=Page[ScanSummary])
async def list_scans(
    session: Session,
    user: CurrentUser,
    q: Annotated[str | None, Query(max_length=100)] = None,
    in_routine: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    base = _history_query(user.id, q, in_routine)
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    scans = (
        await session.execute(
            base.options(selectinload(Scan.items))
            .order_by(Scan.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    items = [
        ScanSummary(
            id=s.id, title=s.title, status=s.status, provider=s.provider,
            prescribed_on=s.prescribed_on, doctor=s.doctor, in_routine=s.in_routine,
            created_at=s.created_at, item_count=len(s.items),
            preview=[i.name for i in s.items[:3]],
        )
        for s in scans
    ]
    return Page[ScanSummary](items=items, total=total or 0, limit=limit, offset=offset)


@router.get("/{scan_id}", response_model=ScanOut)
async def get_scan(scan: OwnedScan):
    return scan_out(scan)


@router.patch("/{scan_id}", response_model=ScanOut)
async def update_scan(body: ScanUpdate, scan: OwnedScan, session: Session):
    sent = body.model_fields_set
    if "title" in sent and body.title:
        scan.title = body.title.strip()
    if "prescribed_on" in sent and body.prescribed_on:
        if body.prescribed_on > date.today() + timedelta(days=1):
            raise ApiError(422, "The prescription date cannot be in the future")
        scan.prescribed_on = body.prescribed_on
    if "doctor" in sent:
        scan.doctor = (body.doctor or "").strip() or None
    if "in_routine" in sent and body.in_routine is not None:
        if body.in_routine and scan.status != ScanStatus.DONE:
            raise ApiError(409, "Wait for the scan to finish before adding it to your routine")
        scan.in_routine = body.in_routine
    await session.commit()
    return scan_out(scan)


@router.delete("/{scan_id}", status_code=204)
async def delete_scan(scan: OwnedScan, session: Session):
    key = scan.image_key
    await session.delete(scan)  # items go with it via the ORM cascade
    await session.commit()
    get_storage().delete(key)


@router.post("/{scan_id}/retry", status_code=202, response_model=ScanAccepted)
async def retry_scan(scan: OwnedScan, session: Session, background: BackgroundTasks):
    if scan.status != ScanStatus.FAILED:
        raise ApiError(409, "Only failed scans can be retried")
    scan.status = ScanStatus.QUEUED
    scan.error = None
    scan.provider = active_name()
    await session.commit()
    background.add_task(process_scan, scan.id)
    return ScanAccepted(id=scan.id, status=scan.status)


@router.get("/{scan_id}/image")
async def scan_image(scan: OwnedScan):
    try:
        data = get_storage().get(scan.image_key)
    except (FileNotFoundError, ValueError):
        raise ApiError(404, "Image not found")
    return Response(
        data,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/{scan_id}/export")
async def export_scan(scan: OwnedScan, format: Literal["csv", "pdf"] = "csv"):
    if scan.status != ScanStatus.DONE:
        raise ApiError(409, "This scan has not finished processing")
    safe = re.sub(r"[^a-z0-9]+", "-", scan.title.lower()).strip("-")
    filename = f"{safe or 'prescription'}.{format}"
    if format == "csv":
        body, media = export.to_csv(scan), "text/csv; charset=utf-8"
    else:
        body, media = export.to_pdf(scan), "application/pdf"
    return Response(
        body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
