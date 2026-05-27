import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TelemetryReadingOut(BaseModel):
    id: uuid.UUID
    time: datetime
    dev_eui: str
    application_id: str | None
    device_profile_id: str | None
    f_cnt: int | None
    f_port: int | None
    rssi: int | None
    snr: float | None
    data_rate: int | None
    raw_payload: str | None
    decoded_data: dict[str, Any]
    is_valid: bool
    validation_errors: list[str] | None
    export_status: str
    exported_at: datetime | None

    model_config = {"from_attributes": True}


class TelemetryPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[TelemetryReadingOut]


class ChirpStackUplinkPayload(BaseModel):
    """Subset of the ChirpStack v4 uplink JSON envelope we care about."""

    deduplicationId: str | None = None
    time: datetime | None = None

    class DeviceInfo(BaseModel):
        tenantId: str | None = None
        applicationId: str | None = None
        applicationName: str | None = None
        deviceProfileId: str | None = None
        deviceProfileName: str | None = None
        deviceName: str | None = None
        devEui: str = ""
        tags: dict[str, str] | None = None

    class RxInfo(BaseModel):
        gatewayId: str | None = None
        rssi: int | None = None
        snr: float | None = None

    deviceInfo: DeviceInfo = Field(default_factory=DeviceInfo)
    devAddr: str | None = None
    adr: bool | None = None
    dr: int | None = None
    fCnt: int | None = None
    fPort: int | None = None
    confirmed: bool | None = None
    data: str | None = None        # base64-encoded application payload
    rxInfo: list[RxInfo] = Field(default_factory=list)
    object: dict[str, Any] | None = None   # pre-decoded by ChirpStack codec


class DirectIngestPayload(BaseModel):
    """Generic ingestion payload for non-LoRaWAN sources."""

    dev_eui: str = Field(..., description="Unique device identifier (any format)")
    time: datetime | None = None
    device_profile_id: str = Field(default="generic")
    data: dict[str, Any] = Field(..., description="Pre-decoded sensor readings")
    metadata: dict[str, Any] | None = None
