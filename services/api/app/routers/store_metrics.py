from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import MetricsServiceDep
from app.schemas.analytics import (
    PeakHoursResponse,
    StoreMetricsSummary,
    ZonePopularity,
)

router = APIRouter(prefix="/store-metrics", tags=["Store Metrics"])


def _default_from() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _default_to() -> datetime:
    return datetime.now(timezone.utc)


@router.get(
    "/summary",
    summary="Store KPI snapshot — visitors, occupancy, dwell, peak hour",
    response_model=StoreMetricsSummary,
)
async def get_store_summary(svc: MetricsServiceDep) -> StoreMetricsSummary:
    return await svc.get_summary()


@router.get(
    "/peak-hours",
    summary="Hourly footfall breakdown",
    response_model=PeakHoursResponse,
)
async def get_peak_hours(
    svc: MetricsServiceDep,
    date: str | None = Query(None, description="YYYY-MM-DD, defaults to today"),
) -> PeakHoursResponse:
    return await svc.get_peak_hours(date)


@router.get(
    "/zones",
    summary="Zone popularity ranked by visit count",
    response_model=list[ZonePopularity],
)
async def get_zone_popularity(
    svc: MetricsServiceDep,
    from_ts: datetime = Query(default_factory=_default_from),
    to_ts: datetime = Query(default_factory=_default_to),
) -> list[ZonePopularity]:
    return await svc.get_zone_popularity(from_ts, to_ts)
