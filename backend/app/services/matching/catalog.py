"""Process wide medicine index, built from the `medicines` table.

The index is read only once built, so it is safe to share across requests and
background tasks. It is cached on disk under a fingerprint of the table, so a
restart with an unchanged catalogue reloads in a fraction of a second.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Medicine
from app.services.matching.index import MedicineIndex

log = logging.getLogger("rxvision.catalog")

_index: MedicineIndex = MedicineIndex([])


def get_index() -> MedicineIndex:
    return _index


def set_index(index: MedicineIndex) -> None:
    global _index
    _index = index


async def load_index(session: AsyncSession, cache_dir: Path | None = None) -> MedicineIndex:
    count, max_id = (
        await session.execute(select(func.count(Medicine.id), func.max(Medicine.id)))
    ).one()
    if not count:
        log.warning("medicine catalogue is empty; run the seed script")
        set_index(MedicineIndex([]))
        return _index

    cache_dir = cache_dir or get_settings().index_cache_dir
    cache = Path(cache_dir) / f"index-{count}-{max_id}.pkl"
    if cache.exists():
        index = await asyncio.to_thread(MedicineIndex.load, cache)
        log.info("medicine index loaded from cache (%d names)", len(index))
    else:
        rows = (await session.execute(select(Medicine.id, Medicine.name))).all()
        log.info("building medicine index for %d names", len(rows))
        index = await asyncio.to_thread(
            MedicineIndex, [r.name for r in rows], [r.id for r in rows]
        )
        try:
            await asyncio.to_thread(index.save, cache)
        except OSError as e:
            log.warning("could not cache index: %s", e)
    set_index(index)
    return index
