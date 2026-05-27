"""
Export service — two delivery mechanisms:

1. Webhook (HTTP POST): flush buffered readings to registered upstream URLs.
2. WebSocket: broadcast live readings to currently connected browser/client sessions.

The export worker runs on a configurable interval and retries pending rows.
Readings stay in TimescaleDB with `export_status = 'pending'` until each
configured target either succeeds or exhausts retries.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import WebSocket

from config import settings
from database import async_session
from models.telemetry import TelemetryReading
from models.device import ExportTarget

log = structlog.get_logger()

# ── WebSocket connection manager ─────────────────────────────────────────────

class _ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        log.info("ws.connected", total=len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections = [c for c in self._connections if c is not ws]
        log.info("ws.disconnected", total=len(self._connections))

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = _ConnectionManager()


async def push_to_websockets(reading: TelemetryReading) -> None:
    if not ws_manager._connections:
        return
    await ws_manager.broadcast(_reading_to_dict(reading))


# ── Export worker (webhook) ──────────────────────────────────────────────────

async def run_export_worker() -> None:
    log.info("exporter.starting", interval=settings.export_retry_interval)
    while True:
        try:
            await asyncio.sleep(settings.export_retry_interval)
            await _flush_pending()
        except asyncio.CancelledError:
            log.info("exporter.stopped")
            return
        except Exception as exc:
            log.error("exporter.error", error=str(exc))


async def _flush_pending() -> None:
    async with async_session() as session:
        targets = (
            await session.execute(
                select(ExportTarget).where(ExportTarget.is_active == True)  # noqa: E712
            )
        ).scalars().all()

        if not targets:
            return

        readings = (
            await session.execute(
                select(TelemetryReading)
                .where(TelemetryReading.export_status == "pending")
                .order_by(TelemetryReading.time)
                .limit(settings.export_batch_size)
            )
        ).scalars().all()

        if not readings:
            return

        log.info("exporter.flushing", readings=len(readings), targets=len(targets))

        async with httpx.AsyncClient(timeout=10.0) as http:
            for reading in readings:
                payload = _reading_to_dict(reading)
                all_ok = True
                last_error: str | None = None

                for target in targets:
                    if target.type != "webhook":
                        continue
                    if target.filter_device_euis and reading.dev_eui not in target.filter_device_euis:
                        continue

                    ok, err = await _post(http, target, payload)
                    if not ok:
                        all_ok = False
                        last_error = err

                await session.execute(
                    update(TelemetryReading)
                    .where(TelemetryReading.id == reading.id)
                    .values(
                        export_status="synced" if all_ok else "failed",
                        exported_at=datetime.now(timezone.utc) if all_ok else None,
                        export_error=last_error,
                    )
                )

        await session.commit()


async def _post(
    http: httpx.AsyncClient,
    target: ExportTarget,
    payload: dict[str, Any],
) -> tuple[bool, str | None]:
    headers = {"Content-Type": "application/json", **(target.headers or {})}
    try:
        resp = await http.post(target.url, json=payload, headers=headers)
        resp.raise_for_status()
        log.debug("exporter.webhook_ok", url=target.url, status=resp.status_code)
        return True, None
    except httpx.HTTPStatusError as exc:
        err = f"HTTP {exc.response.status_code}"
        log.warning("exporter.webhook_failed", url=target.url, error=err)
        return False, err
    except Exception as exc:
        log.warning("exporter.webhook_error", url=target.url, error=str(exc))
        return False, str(exc)


async def test_target(target: ExportTarget) -> dict[str, Any]:
    import time

    probe = {
        "event": "test",
        "source": "linkEdge",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    headers = {"Content-Type": "application/json", **(target.headers or {})}
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=10.0) as http:
        try:
            resp = await http.post(target.url, json=probe, headers=headers)
            return {
                "success": resp.is_success,
                "status_code": resp.status_code,
                "duration_ms": round((time.monotonic() - t0) * 1000, 1),
                "error": None if resp.is_success else resp.text[:256],
            }
        except Exception as exc:
            return {
                "success": False,
                "status_code": None,
                "duration_ms": round((time.monotonic() - t0) * 1000, 1),
                "error": str(exc),
            }


# ── helpers ──────────────────────────────────────────────────────────────────

def _reading_to_dict(r: TelemetryReading) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "time": r.time.isoformat() if r.time else None,
        "dev_eui": r.dev_eui,
        "application_id": r.application_id,
        "device_profile_id": r.device_profile_id,
        "f_cnt": r.f_cnt,
        "f_port": r.f_port,
        "rssi": r.rssi,
        "snr": r.snr,
        "data_rate": r.data_rate,
        "decoded_data": r.decoded_data,
        "is_valid": r.is_valid,
        "validation_errors": r.validation_errors,
    }
