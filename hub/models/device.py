import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Device(Base):
    """Maps a dev_eui to a device profile and optional metadata."""

    __tablename__ = "devices"

    dev_eui: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(128))
    device_profile_id: Mapped[str] = mapped_column(String(64), nullable=False, default="generic")
    application_id: Mapped[str | None] = mapped_column(String(64))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ExportTarget(Base):
    """Upstream destination that receives exported telemetry."""

    __tablename__ = "export_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # "webhook" → HTTP POST  |  "websocket" → push to connected WS clients
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="webhook")
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    headers: Mapped[dict | None] = mapped_column(JSONB)
    # null = forward all devices; list of dev_euis = filtered
    filter_device_euis: Mapped[list | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
