import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class TelemetryReading(Base):
    """One decoded, validated sensor observation.

    `time` is the TimescaleDB partition key — always set to the
    on-device or network-server timestamp, never insertion time.
    """

    __tablename__ = "telemetry_readings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Device identity
    dev_eui: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    application_id: Mapped[str | None] = mapped_column(String(64))
    device_profile_id: Mapped[str | None] = mapped_column(String(64))

    # Packet metadata
    f_cnt: Mapped[int | None] = mapped_column(Integer)
    f_port: Mapped[int | None] = mapped_column(Integer)
    rssi: Mapped[int | None] = mapped_column(Integer)
    snr: Mapped[float | None] = mapped_column(Float)
    data_rate: Mapped[int | None] = mapped_column(Integer)

    # Payload
    raw_payload: Mapped[str | None] = mapped_column(Text)          # base64 original
    decoded_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Validation
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    validation_errors: Mapped[list | None] = mapped_column(JSONB)

    # Export pipeline
    export_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    export_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_telemetry_dev_eui_time", "dev_eui", "time"),
        Index("ix_telemetry_export_status", "export_status", "time"),
    )
