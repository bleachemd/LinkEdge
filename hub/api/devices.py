"""
Device registry API.

POST   /api/v1/devices                    — register a device + profile mapping
GET    /api/v1/devices                    — list all registered devices
GET    /api/v1/devices/{dev_eui}          — single device
PUT    /api/v1/devices/{dev_eui}          — update device
DELETE /api/v1/devices/{dev_eui}          — remove device
GET    /api/v1/devices/profiles           — list loaded device profiles
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.device import Device
from schemas.device import DeviceIn, DeviceOut
from services.decoder import _profiles as loaded_profiles

router = APIRouter()


@router.post("", response_model=DeviceOut, status_code=201)
async def register_device(body: DeviceIn, db: AsyncSession = Depends(get_db)):
    existing = await db.get(Device, body.dev_eui.lower())
    if existing:
        raise HTTPException(status_code=409, detail="Device already registered")

    device = Device(
        dev_eui=body.dev_eui.lower(),
        name=body.name,
        device_profile_id=body.device_profile_id,
        application_id=body.application_id,
        metadata_=body.metadata,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return DeviceOut.model_validate(device)


@router.get("", response_model=list[DeviceOut])
async def list_devices(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Device).order_by(Device.dev_eui))).scalars().all()
    return [DeviceOut.model_validate(r) for r in rows]


@router.get("/profiles", response_model=list[str])
async def list_profiles():
    """Return the IDs of all profiles loaded from disk."""
    return sorted(loaded_profiles.keys())


@router.get("/{dev_eui}", response_model=DeviceOut)
async def get_device(dev_eui: str, db: AsyncSession = Depends(get_db)):
    row = await db.get(Device, dev_eui.lower())
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return DeviceOut.model_validate(row)


@router.put("/{dev_eui}", response_model=DeviceOut)
async def update_device(dev_eui: str, body: DeviceIn, db: AsyncSession = Depends(get_db)):
    device = await db.get(Device, dev_eui.lower())
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    device.name = body.name
    device.device_profile_id = body.device_profile_id
    device.application_id = body.application_id
    device.metadata_ = body.metadata
    device.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(device)
    return DeviceOut.model_validate(device)


@router.delete("/{dev_eui}", status_code=204)
async def delete_device(dev_eui: str, db: AsyncSession = Depends(get_db)):
    device = await db.get(Device, dev_eui.lower())
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    await db.delete(device)
    await db.commit()
