"""
Telemetry query API + live WebSocket stream.

GET  /api/v1/telemetry                  — paginated history
GET  /api/v1/telemetry/{id}             — single reading
GET  /api/v1/telemetry/ws/stream        — WebSocket live feed
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.telemetry import TelemetryReading
from schemas.telemetry import TelemetryPage, TelemetryReadingOut
from services.exporter import ws_manager

router = APIRouter()


@router.get("", response_model=TelemetryPage)
async def list_telemetry(
    dev_eui: str | None = Query(default=None, description="Filter by device EUI"),
    profile_id: str | None = Query(default=None, description="Filter by device profile"),
    valid_only: bool = Query(default=False, description="Return only validated readings"),
    since: datetime | None = Query(default=None, description="Start of time window (ISO 8601)"),
    until: datetime | None = Query(default=None, description="End of time window (ISO 8601)"),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    q = select(TelemetryReading)

    if dev_eui:
        q = q.where(TelemetryReading.dev_eui == dev_eui.lower())
    if profile_id:
        q = q.where(TelemetryReading.device_profile_id == profile_id)
    if valid_only:
        q = q.where(TelemetryReading.is_valid == True)  # noqa: E712
    if since:
        q = q.where(TelemetryReading.time >= since)
    if until:
        q = q.where(TelemetryReading.time <= until)

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar_one()

    rows = (
        await db.execute(q.order_by(TelemetryReading.time.desc()).limit(limit).offset(offset))
    ).scalars().all()

    return TelemetryPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[TelemetryReadingOut.model_validate(r) for r in rows],
    )


@router.get("/{reading_id}", response_model=TelemetryReadingOut)
async def get_reading(reading_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    row = await db.get(TelemetryReading, reading_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    return TelemetryReadingOut.model_validate(row)


@router.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    """Live telemetry stream — emits a JSON object for every new reading."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; the exporter broadcasts readings
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
