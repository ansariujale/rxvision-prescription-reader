import uuid

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, OwnedScan, Session, load_owned_scan
from app.core.errors import ApiError
from app.models import ItemStatus, Medicine, Scan, ScanItem, ScanStatus
from app.schemas import ItemCreate, ItemOut, ItemUpdate, ScanOut

from app.api.routes.scans import scan_out

router = APIRouter(prefix="/scans/{scan_id}/items", tags=["items"])

FIELDS = ("strength", "dose", "frequency", "duration", "timing", "notes")


def _editable(scan: Scan) -> None:
    if scan.status != ScanStatus.DONE:
        raise ApiError(409, "Wait for the scan to finish before editing it")


def _find(scan: Scan, item_id: uuid.UUID) -> ScanItem:
    for item in scan.items:
        if item.id == item_id:
            return item
    raise ApiError(404, "Item not found")


async def _medicine(session, medicine_id: int) -> Medicine:
    medicine = await session.get(Medicine, medicine_id)
    if medicine is None:
        raise ApiError(422, "That medicine is not in the catalogue")
    return medicine


async def _reload(session, item_id: uuid.UUID) -> ScanItem:
    session.expire_all()
    return await session.get(ScanItem, item_id)


@router.post("", status_code=201, response_model=ItemOut)
async def add_item(body: ItemCreate, scan: OwnedScan, session: Session):
    _editable(scan)
    medicine = await _medicine(session, body.medicine_id) if body.medicine_id else None
    name = (body.name or "").strip() or (medicine.name if medicine else "")
    if not name:
        raise ApiError(422, "Give the item a name or pick a medicine")

    position = (
        await session.scalar(select(func.max(ScanItem.position)).where(ScanItem.scan_id == scan.id))
    )
    item = ScanItem(
        scan_id=scan.id,
        position=(position + 1) if position is not None else 0,
        name=name,
        medicine_id=medicine.id if medicine else None,
        status=ItemStatus.MANUAL,
        **body.model_dump(include=set(FIELDS)),
    )
    session.add(item)
    await session.commit()
    return await _reload(session, item.id)


@router.patch("/{item_id}", response_model=ItemOut)
async def update_item(item_id: uuid.UUID, body: ItemUpdate, scan: OwnedScan, session: Session):
    _editable(scan)
    item = _find(scan, item_id)
    sent = body.model_fields_set
    changed = False

    if "medicine_id" in sent:
        if body.medicine_id is None:
            item.medicine_id = None
        else:
            medicine = await _medicine(session, body.medicine_id)
            item.medicine_id = medicine.id
            if "name" not in sent:
                item.name = medicine.name
        item.confidence = None
        changed = True

    if "name" in sent and body.name is not None:
        item.name = body.name.strip()
        changed = True

    for field in FIELDS:
        if field in sent and getattr(item, field) != getattr(body, field):
            setattr(item, field, getattr(body, field))
            changed = True

    if "status" in sent and body.status is not None:
        item.status = body.status
    elif changed and item.status != ItemStatus.MANUAL:
        item.status = ItemStatus.EDITED

    await session.commit()
    return await _reload(session, item.id)


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: uuid.UUID, scan: OwnedScan, session: Session):
    _editable(scan)
    await session.delete(_find(scan, item_id))
    await session.commit()


@router.post("/confirm-all", response_model=ScanOut)
async def confirm_all(scan: OwnedScan, session: Session, user: CurrentUser):
    _editable(scan)
    for item in scan.items:
        if item.status == ItemStatus.SUGGESTED:
            item.status = ItemStatus.CONFIRMED
    await session.commit()
    return scan_out(await load_owned_scan(session, scan.id, user))
