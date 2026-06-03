from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Float, and_, cast, distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anomaly, Event, Session, Zone


class MetricsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def total_visitors_today(self, date_start: datetime, date_end: datetime) -> int:
        stmt = (
            select(func.count(distinct(Event.track_id)))
            .where(
                Event.event_type == "ENTRY",
                Event.timestamp >= date_start,
                Event.timestamp <= date_end,
                Event.track_id.isnot(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def current_occupancy(self) -> int:
        entered = (
            select(func.count(distinct(Event.track_id)))
            .where(Event.event_type == "ENTRY", Event.track_id.isnot(None))
            .scalar_subquery()
        )
        exited = (
            select(func.count(distinct(Event.track_id)))
            .where(Event.event_type == "EXIT", Event.track_id.isnot(None))
            .scalar_subquery()
        )
        stmt = select((entered - exited).label("occupancy"))
        result = await self.session.execute(stmt)
        val = result.scalar_one()
        return max(0, val or 0)

    async def avg_dwell_seconds(self, date_start: datetime, date_end: datetime) -> float:
        stmt = (
            select(func.avg(Session.exited_at - Session.entered_at))
            .where(
                Session.entered_at >= date_start,
                Session.exited_at.isnot(None),
                Session.exited_at <= date_end,
            )
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one()
        if val is None:
            return 0.0
        try:
            return val.total_seconds()
        except AttributeError:
            return float(val)

    async def peak_hour(self, date_start: datetime, date_end: datetime) -> tuple[int | None, int]:
        stmt = (
            select(
                func.date_part("hour", Event.timestamp).label("hr"),
                func.count().label("cnt"),
            )
            .where(
                Event.event_type == "ENTRY",
                Event.timestamp >= date_start,
                Event.timestamp <= date_end,
            )
            .group_by(text("hr"))
            .order_by(text("cnt DESC"))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.fetchone()
        if row is None:
            return None, 0
        return int(row.hr), int(row.cnt)

    async def reentry_count(self, date_start: datetime, date_end: datetime) -> int:
        subq = (
            select(Event.track_id, func.count().label("entries"))
            .where(
                Event.event_type == "ENTRY",
                Event.timestamp >= date_start,
                Event.timestamp <= date_end,
                Event.track_id.isnot(None),
            )
            .group_by(Event.track_id)
            .subquery()
        )
        stmt = select(func.count()).select_from(subq).where(subq.c.entries > 1)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def group_entry_count(self, date_start: datetime, date_end: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(Event)
            .where(
                Event.event_type == "GROUP_ENTRY",
                Event.timestamp >= date_start,
                Event.timestamp <= date_end,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def staff_count(self, date_start: datetime, date_end: datetime) -> int:
        stmt = (
            select(func.count(distinct(Event.track_id)))
            .where(
                Event.person_class == "staff",
                Event.timestamp >= date_start,
                Event.timestamp <= date_end,
                Event.track_id.isnot(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def transaction_count(self, date_start: datetime, date_end: datetime) -> int:
        """Count unique transactions from POS-seeded events (have order_id in metadata)."""
        stmt = (
            select(func.count(distinct(Event.metadata_["order_id"].astext)))
            .where(
                Event.event_type == "ZONE_ENTER",
                Event.timestamp >= date_start,
                Event.timestamp <= date_end,
                Event.metadata_["order_id"].astext.isnot(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def total_gmv(self, date_start: datetime, date_end: datetime) -> float:
        """Sum GMV from POS-seeded ZONE_ENTER events."""
        stmt = (
            select(
                func.coalesce(
                    func.sum(cast(Event.metadata_["gmv"].astext, Float)),
                    0.0,
                )
            )
            .where(
                Event.event_type == "ZONE_ENTER",
                Event.timestamp >= date_start,
                Event.timestamp <= date_end,
                Event.metadata_["order_id"].astext.isnot(None),
            )
        )
        result = await self.session.execute(stmt)
        return float(result.scalar_one() or 0.0)

    async def hourly_footfall(self, date_start: datetime, date_end: datetime) -> list[dict[str, Any]]:
        stmt = (
            select(
                func.date_part("hour", Event.timestamp).label("hr"),
                func.count().label("cnt"),
            )
            .where(
                Event.event_type == "ENTRY",
                Event.timestamp >= date_start,
                Event.timestamp <= date_end,
            )
            .group_by(text("hr"))
            .order_by(text("hr"))
        )
        result = await self.session.execute(stmt)
        return [{"hour": int(r.hr), "count": int(r.cnt)} for r in result]

    async def zone_visit_counts(self, date_start: datetime, date_end: datetime) -> list[dict[str, Any]]:
        """Zone popularity with zone name via LEFT JOIN on zones table."""
        stmt = (
            select(
                Event.zone_id,
                Zone.name.label("zone_name"),
                func.count().label("visit_count"),
            )
            .join(Zone, Zone.id == Event.zone_id, isouter=True)
            .where(
                Event.event_type == "ZONE_ENTER",
                Event.timestamp >= date_start,
                Event.timestamp <= date_end,
                Event.zone_id.isnot(None),
            )
            .group_by(Event.zone_id, Zone.name)
            .order_by(text("visit_count DESC"))
        )
        result = await self.session.execute(stmt)
        return [
            {
                "zone_id": r.zone_id,
                "zone_name": r.zone_name,
                "visit_count": int(r.visit_count),
            }
            for r in result
        ]

    async def open_anomaly_count(self) -> int:
        stmt = select(func.count()).select_from(Anomaly).where(Anomaly.resolved == False)  # noqa: E712
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def events_in_window(self, from_ts: datetime, to_ts: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(Event)
            .where(Event.timestamp >= from_ts, Event.timestamp <= to_ts)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0
