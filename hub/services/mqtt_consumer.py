"""
MQTT consumer — subscribes to ChirpStack application uplink events and
pushes each frame through the decode → validate → persist → export pipeline.
Reconnects automatically on broker disconnects.
"""

import asyncio
import json
from datetime import datetime, timezone

import aiomqtt
import structlog

from config import settings
from database import async_session
from models.telemetry import TelemetryReading
from schemas.telemetry import ChirpStackUplinkPayload
from services import decoder, validator
from services.exporter import push_to_websockets

log = structlog.get_logger()

_RECONNECT_DELAY = 5  # seconds


async def run_mqtt_consumer() -> None:
    """Long-running task; reconnects on failure."""
    decoder.load_profiles()
    log.info("mqtt_consumer.starting", host=settings.mqtt_host, port=settings.mqtt_port)

    while True:
        try:
            await _consume()
        except aiomqtt.MqttError as exc:
            log.warning("mqtt_consumer.disconnected", error=str(exc), retry_in=_RECONNECT_DELAY)
            await asyncio.sleep(_RECONNECT_DELAY)
        except asyncio.CancelledError:
            log.info("mqtt_consumer.stopped")
            return


async def _consume() -> None:
    kwargs: dict = dict(hostname=settings.mqtt_host, port=settings.mqtt_port)
    if settings.mqtt_username:
        kwargs["username"] = settings.mqtt_username
        kwargs["password"] = settings.mqtt_password

    async with aiomqtt.Client(**kwargs) as client:
        await client.subscribe(settings.mqtt_uplink_topic)
        log.info("mqtt_consumer.subscribed", topic=settings.mqtt_uplink_topic)

        async for message in client.messages:
            try:
                await _handle(message)
            except Exception as exc:
                log.error("mqtt_consumer.handle_error", error=str(exc))


async def _handle(message: aiomqtt.Message) -> None:
    raw_json = message.payload
    if isinstance(raw_json, (bytes, bytearray)):
        raw_json = raw_json.decode("utf-8", errors="replace")

    envelope = ChirpStackUplinkPayload.model_validate_json(raw_json)
    dev_info = envelope.deviceInfo
    dev_eui = dev_info.devEui.lower().replace(":", "")

    # Look up the profile registered for this device (fallback: generic)
    profile_id = await _lookup_profile(dev_eui) or dev_info.deviceProfileId or "generic"

    # If ChirpStack already decoded via a codec, use that; otherwise decode raw bytes
    if envelope.object:
        decoded = envelope.object
    else:
        decoded = decoder.decode(envelope.data, profile_id)

    is_valid, errors = validator.validate(dev_eui, decoded, profile_id)

    best_rx = envelope.rxInfo[0] if envelope.rxInfo else None
    ts = envelope.time or datetime.now(timezone.utc)

    reading = TelemetryReading(
        time=ts,
        dev_eui=dev_eui,
        application_id=dev_info.applicationId,
        device_profile_id=profile_id,
        f_cnt=envelope.fCnt,
        f_port=envelope.fPort,
        rssi=best_rx.rssi if best_rx else None,
        snr=best_rx.snr if best_rx else None,
        data_rate=envelope.dr,
        raw_payload=envelope.data,
        decoded_data=decoded,
        is_valid=is_valid,
        validation_errors=errors or None,
        export_status="pending",
    )

    async with async_session() as session:
        session.add(reading)
        await session.commit()
        await session.refresh(reading)

    log.info(
        "mqtt_consumer.reading_stored",
        dev_eui=dev_eui, valid=is_valid, id=str(reading.id),
    )

    # Immediately push to any connected WebSocket clients
    await push_to_websockets(reading)


async def _lookup_profile(dev_eui: str) -> str | None:
    from models.device import Device
    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(
            select(Device.device_profile_id).where(Device.dev_eui == dev_eui)
        )
        row = result.scalar_one_or_none()
        return row
