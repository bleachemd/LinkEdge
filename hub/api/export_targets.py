"""
Export-target management API.

POST   /api/v1/export-targets                   — add a target
GET    /api/v1/export-targets                   — list targets
PUT    /api/v1/export-targets/{id}              — update a target
DELETE /api/v1/export-targets/{id}              — remove a target
POST   /api/v1/export-targets/{id}/test         — fire a test payload
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.device import ExportTarget
from schemas.export import ExportTargetIn, ExportTargetOut, ExportTestResult
from services.exporter import test_target

router = APIRouter()


@router.post("", response_model=ExportTargetOut, status_code=201)
async def add_target(body: ExportTargetIn, db: AsyncSession = Depends(get_db)):
    target = ExportTarget(**body.model_dump())
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return ExportTargetOut.model_validate(target)


@router.get("", response_model=list[ExportTargetOut])
async def list_targets(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(ExportTarget).order_by(ExportTarget.created_at))
    ).scalars().all()
    return [ExportTargetOut.model_validate(r) for r in rows]


@router.put("/{target_id}", response_model=ExportTargetOut)
async def update_target(
    target_id: uuid.UUID, body: ExportTargetIn, db: AsyncSession = Depends(get_db)
):
    target = await db.get(ExportTarget, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Export target not found")

    for key, val in body.model_dump().items():
        setattr(target, key, val)

    await db.commit()
    await db.refresh(target)
    return ExportTargetOut.model_validate(target)


@router.delete("/{target_id}", status_code=204)
async def delete_target(target_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    target = await db.get(ExportTarget, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Export target not found")
    await db.delete(target)
    await db.commit()


@router.post("/{target_id}/test", response_model=ExportTestResult)
async def fire_test(target_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    target = await db.get(ExportTarget, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Export target not found")
    if target.type != "webhook":
        raise HTTPException(status_code=400, detail="Test only supported for webhook targets")
    result = await test_target(target)
    return ExportTestResult(**result)
