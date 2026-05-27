from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DeviceIn(BaseModel):
    dev_eui: str = Field(..., max_length=16)
    name: str | None = Field(default=None, max_length=128)
    device_profile_id: str = Field(default="generic", max_length=64)
    application_id: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] | None = None


class DeviceOut(BaseModel):
    dev_eui: str
    name: str | None
    device_profile_id: str
    application_id: str | None
    metadata_: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
