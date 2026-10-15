import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.db import session as db
from app.services.matching.catalog import load_index
from app.services.pipeline import pending_scan_ids, requeue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("rxvision")

_background: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db.configure()
    async with db.session_factory()() as session:
        await load_index(session, settings.index_cache_dir)

    # Scans interrupted by a restart would otherwise sit in "processing" forever.
    for scan_id in await pending_scan_ids():
        log.info("resuming scan %s", scan_id)
        task = asyncio.create_task(requeue(scan_id))
        _background.add(task)
        task.add_done_callback(_background.discard)

    yield
    await db.engine().dispose()


def create_app(*, run_lifespan: bool = True) -> FastAPI:
    app = FastAPI(
        title="RxVision API",
        version="2.0.0",
        lifespan=lifespan if run_lifespan else None,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    install_error_handlers(app)
    app.include_router(api)
    return app


app = create_app()
