from datetime import datetime, timedelta, timezone

import structlog

from app.repositories.anomalies import AnomalyRepository
from app.repositories.events import EventRepository
from app.schemas.analytics import FunnelResponse, FunnelStage
from app.schemas.events import EventType

logger = structlog.get_logger(__name__)

# Ordered funnel: each stage is a subset of the previous by definition in store context
_FUNNEL_STAGES = [
    ("Entered Store", EventType.ENTRY),
    ("Visited Zone", EventType.ZONE_ENTER),
    ("Dwelled", EventType.DWELL_STARTED),
    ("Exited Store", EventType.EXIT),
]


class AnalyticsService:
    def __init__(self, event_repo: EventRepository, anomaly_repo: AnomalyRepository) -> None:
        self.event_repo = event_repo
        self.anomaly_repo = anomaly_repo

    async def get_funnel(self, from_ts: datetime, to_ts: datetime) -> FunnelResponse:
        counts = await self.event_repo.funnel_counts(from_ts, to_ts)
        logger.debug("funnel_counts", counts=counts)

        stages: list[FunnelStage] = []
        prev_count: int | None = None

        for label, event_type in _FUNNEL_STAGES:
            count = counts.get(event_type.value, 0)
            drop_off = (prev_count - count) if prev_count is not None else 0
            conversion_rate = (count / prev_count * 100.0) if prev_count and prev_count > 0 else 100.0

            stages.append(
                FunnelStage(
                    stage=label,
                    count=count,
                    drop_off=max(drop_off, 0),
                    conversion_rate=round(conversion_rate, 2),
                )
            )
            prev_count = count

        return FunnelResponse(from_ts=from_ts, to_ts=to_ts, stages=stages)
