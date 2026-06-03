from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from app.dependencies import AnalyticsServiceDep
from app.schemas.analytics import FunnelResponse

router = APIRouter(prefix="/funnel", tags=["Analytics"])


def _default_from() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=24)


def _default_to() -> datetime:
    return datetime.now(timezone.utc)


@router.get(
    "",
    summary="Customer journey conversion funnel",
    response_model=FunnelResponse,
)
async def get_funnel(
    svc: AnalyticsServiceDep,
    from_ts: datetime = Query(default_factory=_default_from),
    to_ts: datetime = Query(default_factory=_default_to),
) -> FunnelResponse:
    return await svc.get_funnel(from_ts, to_ts)
