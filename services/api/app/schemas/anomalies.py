from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class AnomalyType(StrEnum):
    LOITERING = "LOITERING"
    CROWD_SURGE = "CROWD_SURGE"
    LONG_STAY = "LONG_STAY"
    EXCESS_REENTRY = "EXCESS_REENTRY"
    CAMERA_FAILURE = "CAMERA_FAILURE"
    ABANDONED_OBJECT = "ABANDONED_OBJECT"
    TAILGATE = "TAILGATE"


class AnomalySeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str | None
    anomaly_type: str
    severity: str
    resolved: bool
    resolved_at: datetime | None
    resolved_by: str | None
    notes: str | None
    detected_at: datetime


class AnomalyResolve(BaseModel):
    notes: str | None = None
    resolved_by: str = Field(..., min_length=1, max_length=255)


class AnomalyFilter(BaseModel):
    resolved: bool | None = False
    severity: AnomalySeverity | None = None
    anomaly_type: AnomalyType | None = None
    from_ts: datetime | None = None
    to_ts: datetime | None = None
    limit: int = Field(default=50, ge=1, le=500)
    cursor: str | None = None
