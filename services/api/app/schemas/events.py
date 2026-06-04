from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import BBox


class EventType(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    STAFF_DETECTED = "STAFF_DETECTED"
    GROUP_ENTRY = "GROUP_ENTRY"
    DWELL_STARTED = "DWELL_STARTED"
    DWELL_ENDED = "DWELL_ENDED"
    ANOMALY = "ANOMALY"


class PersonClass(StrEnum):
    CUSTOMER = "customer"
    STAFF = "staff"
    UNKNOWN = "unknown"


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    timestamp: datetime
    camera_id: str | None
    track_id: str | None
    session_id: str | None
    zone_id: str | None
    group_id: str | None
    person_class: str | None
    confidence: float | None
    bbox: BBox | None = None
    metadata_: dict[str, Any] | None = Field(None, serialization_alias="metadata")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class EventFilter(BaseModel):
    event_type: list[EventType] | None = None
    camera_id: str | None = None
    zone_id: str | None = None
    session_id: str | None = None
    person_class: PersonClass | None = None
    from_ts: datetime | None = None
    to_ts: datetime | None = None
    limit: int = Field(default=50, ge=1, le=500)
    cursor: str | None = None
