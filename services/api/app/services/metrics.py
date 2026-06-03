import time
from datetime import datetime, timedelta, timezone

import structlog

from app.repositories.metrics import MetricsRepository
from app.schemas.analytics import (
    HourBucket,
    PeakHoursResponse,
    StoreMetricsSummary,
    ZonePopularity,
)

logger = structlog.get_logger(__name__)

_start_time = time.monotonic()


def _today_window() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


class MetricsService:
    def __init__(self, repo: MetricsRepository) -> None:
        self.repo = repo

    async def get_summary(self) -> StoreMetricsSummary:
        date_start, date_end = _today_window()

        total = await self.repo.total_visitors_today(date_start, date_end)
        occupancy = await self.repo.current_occupancy()
        avg_dwell = await self.repo.avg_dwell_seconds(date_start, date_end)
        peak_hr, peak_cnt = await self.repo.peak_hour(date_start, date_end)
        reentry = await self.repo.reentry_count(date_start, date_end)
        groups = await self.repo.group_entry_count(date_start, date_end)
        staff = await self.repo.staff_count(date_start, date_end)
        transactions = await self.repo.transaction_count(date_start, date_end)
        gmv = await self.repo.total_gmv(date_start, date_end)

        reentry_rate = round((reentry / total * 100) if total > 0 else 0.0, 2)
        # Conversion = unique buyers / total visitors
        conversion = round((transactions / total * 100) if total > 0 else 0.0, 2)

        logger.debug(
            "store_metrics_summary",
            total=total,
            occupancy=occupancy,
            peak_hr=peak_hr,
            transactions=transactions,
            conversion_pct=conversion,
        )

        return StoreMetricsSummary(
            as_of=date_end,
            total_visitors_today=total,
            current_occupancy=occupancy,
            unique_visitors_today=total - reentry,
            avg_dwell_seconds=round(avg_dwell, 1),
            peak_hour=peak_hr,
            peak_hour_count=peak_cnt,
            reentry_rate_pct=reentry_rate,
            group_entry_count=groups,
            staff_count=staff,
            conversion_rate_pct=conversion,
            total_transactions=transactions,
            total_gmv=round(gmv, 2),
        )

    async def get_peak_hours(self, date: str | None = None) -> PeakHoursResponse:
        if date:
            dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            date_start = dt
            date_end = dt + timedelta(days=1)
        else:
            date_start, date_end = _today_window()
            date_start = date_start.replace(hour=0, minute=0, second=0, microsecond=0)

        rows = await self.repo.hourly_footfall(date_start, date_end)
        buckets = [HourBucket(hour=r["hour"], count=r["count"]) for r in rows]
        date_str = date or date_start.strftime("%Y-%m-%d")
        return PeakHoursResponse(date=date_str, buckets=buckets)

    async def get_zone_popularity(self, date_start: datetime, date_end: datetime) -> list[ZonePopularity]:
        rows = await self.repo.zone_visit_counts(date_start, date_end)
        return [
            ZonePopularity(
                zone_id=r["zone_id"],
                zone_name=r.get("zone_name"),
                visit_count=r["visit_count"],
                avg_dwell_seconds=0.0,
            )
            for r in rows
        ]
