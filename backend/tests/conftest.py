import io
import os

os.environ.setdefault("OCR_PROVIDER", "mock")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

import httpx
import pytest
from PIL import Image
from sqlalchemy import insert

from app.core.config import SAMPLE_CSV
from app.db import session as db
from app.db.base import Base
from app.main import create_app
from app.models import Medicine
from app.scripts.seed import read_rows
from app.services.matching.catalog import set_index
from app.services.matching.index import MedicineIndex
from app.services.ocr import factory
from app.services.ocr.mock import MockProvider
from app.services.storage import LocalStorage, set_storage

SAMPLE_ROWS = list(read_rows(SAMPLE_CSV))


@pytest.fixture(scope="session")
def sample_index() -> MedicineIndex:
    return MedicineIndex([r["name"] for r in SAMPLE_ROWS], list(range(1, len(SAMPLE_ROWS) + 1)))


@pytest.fixture
async def app(tmp_path, sample_index):
    db.configure(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with db.engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            insert(Medicine), [{"id": i, **row} for i, row in enumerate(SAMPLE_ROWS, 1)]
        )
    set_storage(LocalStorage(tmp_path / "images"))
    set_index(sample_index)
    factory.set_provider(MockProvider(delay=0))
    yield create_app(run_lifespan=False)
    factory.set_provider(None)
    await db.engine().dispose()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def register(client, email="asha@example.com", password="correct horse", name="Asha"):
    r = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password, "name": name}
    )
    assert r.status_code == 201, r.text
    return r


@pytest.fixture
async def user_client(client):
    await register(client)
    return client


def jpeg_bytes(width=800, height=600, color=(240, 240, 235)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG")
    return buf.getvalue()
