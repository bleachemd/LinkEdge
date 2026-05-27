import asyncio
import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db

logging.basicConfig(level=settings.log_level.upper())
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.getLevelName(settings.log_level.upper())
    )
)

log = structlog.get_logger()

_background_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("hub.startup", version="1.0.0")

    await init_db()
    log.info("db.ready")

    # Lazy imports to avoid circular deps at module load time
    from services.mqtt_consumer import run_mqtt_consumer
    from services.exporter import run_export_worker

    _background_tasks.append(asyncio.create_task(run_mqtt_consumer(), name="mqtt"))
    _background_tasks.append(asyncio.create_task(run_export_worker(), name="exporter"))

    log.info("background_tasks.started", count=len(_background_tasks))
    yield

    for task in _background_tasks:
        task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
    log.info("hub.shutdown")


app = FastAPI(
    title="LinkEdge Hub",
    description="Universal local hub — collects, validates, and buffers sensor telemetry for any upstream platform.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.telemetry import router as telemetry_router
from api.devices import router as devices_router
from api.export_targets import router as export_router
from api.ingest import router as ingest_router

app.include_router(telemetry_router, prefix="/api/v1/telemetry", tags=["Telemetry"])
app.include_router(devices_router, prefix="/api/v1/devices", tags=["Devices"])
app.include_router(export_router, prefix="/api/v1/export-targets", tags=["Export Targets"])
app.include_router(ingest_router, prefix="/api/v1/ingest", tags=["Ingest"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
