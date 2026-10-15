"""Load a medicine CSV into the catalogue.

    python -m app.scripts.seed                    # bundled sample, skip if not empty
    python -m app.scripts.seed --csv path.csv     # e.g. the full 254k dataset
    python -m app.scripts.seed --csv path.csv --replace

Accepts the column names of the public A-Z India medicine dataset
(`manufacturer_name`, `pack_size_label`, `short_composition1/2`, `price(₹)`)
as well as plain ones (`manufacturer`, `pack_size`, `composition`, `price`).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import delete, func, insert, select

from app.core.config import get_settings
from app.db import session as db
from app.models import Medicine

BATCH = 5000


def _first(row: dict, *keys: str) -> str | None:
    for k in keys:
        v = (row.get(k) or "").strip()
        if v:
            return v
    return None


def _price(raw: str | None) -> Decimal | None:
    if not raw:
        return None
    try:
        return Decimal(raw.replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _composition(row: dict) -> str | None:
    plain = _first(row, "composition")
    if plain:
        return plain
    parts = [p for p in (_first(row, "short_composition1"), _first(row, "short_composition2")) if p]
    return " + ".join(" ".join(p.split()) for p in parts) or None


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = _first(row, "name")
            if not name:
                continue
            yield {
                "name": name[:300],
                "manufacturer": (_first(row, "manufacturer_name", "manufacturer") or "")[:200] or None,
                "type": (_first(row, "type") or "")[:50] or None,
                "pack_size": (_first(row, "pack_size_label", "pack_size") or "")[:120] or None,
                "composition": _composition(row),
                "price": _price(_first(row, "price(₹)", "price")),
                "uses": _first(row, "uses"),
            }


async def seed(csv_path: Path, replace: bool = False) -> int:
    async with db.session_factory()() as session:
        count = await session.scalar(select(func.count(Medicine.id)))
        if count and not replace:
            print(f"catalogue already has {count:,} medicines; use --replace to reload")
            return 0
        if replace:
            await session.execute(delete(Medicine))

        total, batch = 0, []
        for row in read_rows(csv_path):
            batch.append(row)
            if len(batch) >= BATCH:
                await session.execute(insert(Medicine), batch)
                total += len(batch)
                batch = []
                print(f"  {total:,}", end="\r", flush=True)
        if batch:
            await session.execute(insert(Medicine), batch)
            total += len(batch)
        await session.commit()
    print(f"loaded {total:,} medicines from {csv_path}")
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    path = args.csv or get_settings().medicine_csv
    if not Path(path).exists():
        print(f"no such file: {path}", file=sys.stderr)
        return 1
    db.configure()
    asyncio.run(seed(Path(path), args.replace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
