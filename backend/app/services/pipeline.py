"""The background job: read a scan's image and turn it into items.

`process_scan` takes only an id and reads everything else from the database, so
it can move from FastAPI background tasks to a real queue without changes.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select

from app.db.session import session_factory
from app.models import ItemStatus, Scan, ScanItem, ScanStatus, utcnow
from app.services.dosage import normalise_frequency, parse_line
from app.services.matching.catalog import get_index
from app.services.matching.index import Match, MedicineIndex
from app.services.ocr.base import OcrResult, ProviderError
from app.services.ocr.factory import get_provider
from app.services.storage import get_storage

log = logging.getLogger("rxvision.pipeline")

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class Draft:
    name: str
    medicine_id: int | None
    confidence: float | None
    strength: str | None = None
    dose: str | None = None
    frequency: str | None = None
    duration: str | None = None
    timing: str | None = None
    notes: str | None = None
    source_line: str | None = None


def _query(name: str, strength: str | None) -> str:
    """Name plus the strength number, so 'Augmentin' + '625 mg' looks up 'augmentin 625'."""
    if strength:
        m = _NUMBER.search(strength)
        if m and m.group(0) not in name:
            return f"{name} {m.group(0)}"
    return name


MAX_PREFIX_TRIES = 4


def best_match(index: MedicineIndex, name: str, strength: str | None, threshold: float,
               min_length: int = 6) -> Match | None:
    """Match a name, also trying shorter leading slices of it.

    Prescription lines often trail off into instructions ("Dolo 650 for fever"),
    and those extra words drag the whole-line score under the threshold. The
    medicine name almost always comes first, so dropping words from the end
    recovers it. The highest score across the tries wins.
    """
    tokens = name.split()
    tries = [name] + [" ".join(tokens[:k]) for k in range(len(tokens) - 1, 0, -1)][:MAX_PREFIX_TRIES]
    best: Match | None = None
    for text in tries:
        hit = index.match(_query(text, strength), threshold, min_length=min_length)
        if hit and (best is None or hit.score > best.score):
            best = hit
            if hit.score >= 100:
                break
    return best


def drafts_from_result(result: OcrResult, index: MedicineIndex, threshold: float) -> list[Draft]:
    drafts: list[Draft] = []

    if result.medicines is not None:
        # Structured provider: trust that each entry is a medicine, but verify
        # the name against the catalogue. Unmatched entries are kept and flagged.
        for m in result.medicines:
            parsed = parse_line(m.name)
            strength = m.strength or parsed.strength
            hit = best_match(index, parsed.name_part or m.name, strength, threshold, min_length=3)
            drafts.append(
                Draft(
                    name=hit.name if hit else m.name,
                    medicine_id=hit.medicine_id if hit else None,
                    confidence=round(hit.score / 100, 3) if hit else None,
                    strength=strength,
                    dose=m.dose,
                    frequency=normalise_frequency(m.frequency),
                    duration=m.duration,
                    timing=m.timing,
                    notes=m.notes,
                    source_line=m.source_line or m.name,
                )
            )
    else:
        # Text provider: every line is a candidate; only lines that match the
        # catalogue become items, the rest is letterhead and instructions.
        for line in result.lines:
            parsed = parse_line(line)
            if not parsed.name_part:
                continue
            hit = best_match(index, parsed.name_part, parsed.strength, threshold)
            if hit is None:
                continue
            drafts.append(
                Draft(
                    name=hit.name,
                    medicine_id=hit.medicine_id,
                    confidence=round(hit.score / 100, 3),
                    strength=parsed.strength,
                    dose=parsed.dose,
                    frequency=parsed.frequency,
                    duration=parsed.duration,
                    timing=parsed.timing,
                    source_line=parsed.source,
                )
            )

    return dedupe(drafts)


def dedupe(drafts: list[Draft]) -> list[Draft]:
    """One item per catalogue entry, keeping the more confident reading."""
    best: dict[int, int] = {}
    out: list[Draft | None] = []
    for d in drafts:
        if d.medicine_id is None:
            out.append(d)
            continue
        if d.medicine_id in best:
            kept = out[best[d.medicine_id]]
            if (d.confidence or 0) > (kept.confidence or 0):
                out[best[d.medicine_id]] = d
            continue
        best[d.medicine_id] = len(out)
        out.append(d)
    return [d for d in out if d is not None]


async def process_scan(scan_id: uuid.UUID, threshold: float | None = None) -> None:
    from app.core.config import get_settings

    threshold = threshold if threshold is not None else get_settings().match_threshold
    factory = session_factory()

    async with factory() as session:
        scan = await session.get(Scan, scan_id)
        if scan is None or scan.status not in ScanStatus.PENDING:
            return
        scan.status = ScanStatus.PROCESSING
        scan.error = None
        await session.commit()
        image_key, provider_name = scan.image_key, scan.provider

    started = time.perf_counter()
    try:
        image = get_storage().get(image_key)
        provider = get_provider(provider_name)
        result = await provider.read(image, "image/jpeg")
        drafts = drafts_from_result(result, get_index(), threshold)
    except ProviderError as e:
        log.warning("scan %s failed: %s", scan_id, e)
        await _fail(scan_id, e.user_message, started)
        return
    except Exception:
        log.exception("scan %s crashed", scan_id)
        await _fail(scan_id, "Something went wrong while reading this prescription.", started)
        return

    async with factory() as session:
        scan = await session.get(Scan, scan_id)
        if scan is None:  # deleted while processing
            return
        await session.execute(delete(ScanItem).where(ScanItem.scan_id == scan_id))
        for position, d in enumerate(drafts):
            session.add(
                ScanItem(
                    scan_id=scan_id,
                    position=position,
                    status=ItemStatus.SUGGESTED,
                    **d.__dict__,
                )
            )
        scan.raw_text = result.text
        if result.doctor and not scan.doctor:
            scan.doctor = result.doctor
        if result.prescribed_on:
            scan.prescribed_on = result.prescribed_on
        scan.status = ScanStatus.DONE
        scan.completed_at = utcnow()
        scan.duration_ms = int((time.perf_counter() - started) * 1000)
        await session.commit()


async def _fail(scan_id: uuid.UUID, message: str, started: float) -> None:
    async with session_factory()() as session:
        scan = await session.get(Scan, scan_id)
        if scan is None:
            return
        scan.status = ScanStatus.FAILED
        scan.error = message
        scan.completed_at = utcnow()
        scan.duration_ms = int((time.perf_counter() - started) * 1000)
        await session.commit()


async def pending_scan_ids() -> list[uuid.UUID]:
    async with session_factory()() as session:
        rows = await session.execute(select(Scan.id).where(Scan.status.in_(ScanStatus.PENDING)))
        return list(rows.scalars())


async def requeue(scan_id: uuid.UUID) -> None:
    """Reset a scan left mid-flight by a crash so process_scan will pick it up."""
    async with session_factory()() as session:
        scan = await session.get(Scan, scan_id)
        if scan is not None and scan.status == ScanStatus.PROCESSING:
            scan.status = ScanStatus.QUEUED
            await session.commit()
    await process_scan(scan_id)
