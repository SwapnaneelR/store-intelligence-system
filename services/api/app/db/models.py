from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: __import__("uuid").uuid4().hex)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(Text)
    rtsp_url: Mapped[str | None] = mapped_column(Text)
    resolution_w: Mapped[int | None] = mapped_column(Integer)
    resolution_h: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pass  # zones relationship removed — Zone.camera_id is now plain varchar


class StoreLayout(Base):
    __tablename__ = "store_layouts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: __import__("uuid").uuid4().hex)
    version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    floor_plan: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pass  # zones relationship removed — Zone.layout_id is now plain varchar


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: __import__("uuid").uuid4().hex)
    layout_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    camera_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(100), nullable=False)
    polygon: Mapped[list] = mapped_column(JSONB, nullable=False)
    color: Mapped[str | None] = mapped_column(String(50))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: __import__("uuid").uuid4().hex)
    track_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    camera_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    person_class: Mapped[str] = mapped_column(String(50), default="customer")
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entry_zone_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    exit_zone_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    pass  # events relationship removed — session_id on Event is now plain varchar


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: __import__("uuid").uuid4().hex)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    camera_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    track_id: Mapped[str | None] = mapped_column(String(255))
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zone_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    group_id: Mapped[str | None] = mapped_column(String(255))
    person_class: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Float)
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    # Relationships removed — camera_id/session_id/zone_id are now plain varchar columns

    __table_args__ = (
        Index("idx_events_type_ts", "event_type", "timestamp"),
        Index("idx_events_camera_ts", "camera_id", "timestamp"),
        Index("idx_events_zone", "zone_id", "timestamp"),
        Index("idx_events_session", "session_id"),
    )


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: __import__("uuid").uuid4().hex)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    anomaly_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_anomalies_resolved_detected", "resolved", "detected_at"),
        Index("idx_anomalies_severity", "severity", "detected_at"),
    )
