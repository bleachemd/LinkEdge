"""
Direct HTTP ingestion endpoint.

POST /api/v1/ingest        — accept pre-decoded data from any source
                             (ChirpStack HTTP integration, custom sensors,
                              smart home gateways, etc.)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from database import get_db
from models.telemetry import TelemetryReading
from schemas.telemetry import DirectIngestPayload, TelemetryReadingOut
from services import decoder, validator
from services.exporter import push_to_websockets

log = structlog.get_logger()
router = APIRouter()


@router.post("", response_model=TelemetryReadingOut, status_code=201)
async def ingest(body: DirectIngestPayload, db: AsyncSession = Depends(get_db)):
    """
    Accept a pre-decoded telemetry payload from any upstream source.

    The `device_profile_id` selects which validation rules to apply.
    If the profile is unknown the `generic` profile is used (no rules).
    """
    dev_eui = body.dev_eui.lower()
    profile_id = body.device_profile_id or "generic"

    decoded = decoder.decode_direct(body.data, profile_id)
    is_valid, errors = validator.validate(dev_eui, decoded, profile_id)

    reading = TelemetryReading(
        time=body.time or datetime.now(timezone.utc),
        dev_eui=dev_eui,
        device_profile_id=profile_id,
        decoded_data=decoded,
        is_valid=is_valid,
        validation_errors=errors or None,
        export_status="pending",
    )

    db.add(reading)
    await db.commit()
    await db.refresh(reading)

    log.info("ingest.stored", dev_eui=dev_eui, valid=is_valid, id=str(reading.id))
    await push_to_websockets(reading)

    return TelemetryReadingOut.model_validate(reading)
