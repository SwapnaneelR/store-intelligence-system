from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import BBox
from app.schemas.events import EventType, PersonClass


class EventIngest(BaseModel):
    event_type: EventType
    timestamp: datetime
    camera_id: str | None = None
    track_id: str | None = None
    session_id: str | None = None
    zone_id: str | None = None
    group_id: str | None = None
    person_class: PersonClass | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    bbox: BBox | None = None
    metadata: dict[str, Any] | None = None


class EventIngestResponse(BaseModel):
    id: str
    event_type: str
    timestamp: datetime


class BatchIngest(BaseModel):
    events: list[EventIngest] = Field(..., min_length=1, max_length=500)


class BatchIngestResponse(BaseModel):
    inserted: int
    ids: list[str]
