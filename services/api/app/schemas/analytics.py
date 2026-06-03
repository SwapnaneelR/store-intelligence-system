from datetime import datetime
from pydantic import BaseModel


class FunnelStage(BaseModel):
    stage: str
    count: int
    drop_off: int
    conversion_rate: float


class FunnelResponse(BaseModel):
    from_ts: datetime
    to_ts: datetime
    stages: list[FunnelStage]


class FootfallBucket(BaseModel):
    ts: datetime
    total: int
    customers: int
    staff: int


class FootfallResponse(BaseModel):
    from_ts: datetime
    to_ts: datetime
    granularity: str
    buckets: list[FootfallBucket]


class ZoneDwellStats(BaseModel):
    zone_id: str
    zone_name: str | None
    avg_dwell_s: float
    median_dwell_s: float
    p95_dwell_s: float
    visit_count: int


class MetricsSnapshot(BaseModel):
    active_tracks: int
    events_last_hour: int
    open_anomalies: int
    cameras_online: int
    uptime_seconds: float


class StoreMetricsSummary(BaseModel):
    as_of: datetime
    total_visitors_today: int
    current_occupancy: int
    unique_visitors_today: int
    avg_dwell_seconds: float
    peak_hour: int | None
    peak_hour_count: int
    reentry_rate_pct: float
    group_entry_count: int
    staff_count: int
    conversion_rate_pct: float
    total_transactions: int
    total_gmv: float


class HourBucket(BaseModel):
    hour: int
    count: int


class ZonePopularity(BaseModel):
    zone_id: str
    zone_name: str | None
    visit_count: int
    avg_dwell_seconds: float


class FootfallTimeline(BaseModel):
    from_ts: datetime
    to_ts: datetime
    granularity: str
    buckets: list[FootfallBucket]


class ZoneDwellSummary(BaseModel):
    zones: list[ZoneDwellStats]


class PeakHoursResponse(BaseModel):
    date: str
    buckets: list[HourBucket]
