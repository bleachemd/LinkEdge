import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ExportTargetIn(BaseModel):
    name: str = Field(..., max_length=128)
    type: str = Field(default="webhook", pattern=r"^(webhook|websocket)$")
    url: str = Field(..., max_length=2048)
    headers: dict[str, str] | None = None
    filter_device_euis: list[str] | None = Field(
        default=None,
        description="Restrict export to these dev_euis. Null = forward all.",
    )
    is_active: bool = True

    @field_validator("url")
    @classmethod
    def url_must_have_scheme(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v


class ExportTargetOut(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    url: str
    headers: dict[str, Any] | None
    filter_device_euis: list[str] | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportTestResult(BaseModel):
    success: bool
    status_code: int | None = None
    error: str | None = None
    duration_ms: float | None = None
