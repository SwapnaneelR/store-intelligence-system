import base64
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event
from app.repositories.base import BaseRepository
from app.schemas.events import EventFilter


def _encode_cursor(event_id: str, timestamp: datetime) -> str:
    raw = f"{timestamp.isoformat()}|{event_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    ts_str, event_id = raw.split("|", 1)
    return datetime.fromisoformat(ts_str), event_id


class EventRepository(BaseRepository[Event]):
    model = Event

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_events(self, filters: EventFilter) -> tuple[list[Event], str | None]:
        conditions: list[Any] = []

        if filters.event_type:
            conditions.append(Event.event_type.in_([e.value for e in filters.event_type]))
        if filters.camera_id:
            conditions.append(Event.camera_id == filters.camera_id)
        if filters.zone_id:
            conditions.append(Event.zone_id == filters.zone_id)
        if filters.session_id:
            conditions.append(Event.session_id == filters.session_id)
        if filters.person_class:
            conditions.append(Event.person_class == filters.person_class.value)
        if filters.from_ts:
            conditions.append(Event.timestamp >= filters.from_ts)
        if filters.to_ts:
            conditions.append(Event.timestamp <= filters.to_ts)

        if filters.cursor:
            cursor_ts, cursor_id = _decode_cursor(filters.cursor)
            conditions.append(
                and_(
                    Event.timestamp <= cursor_ts,
                    Event.id < cursor_id,
                )
            )

        stmt = (
            select(Event)
            .where(*conditions)
            .order_by(Event.timestamp.desc(), Event.id.desc())
            .limit(filters.limit + 1)
        )

        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor: str | None = None
        if len(rows) > filters.limit:
            rows = rows[: filters.limit]
            last = rows[-1]
            next_cursor = _encode_cursor(last.id, last.timestamp)

        return rows, next_cursor

    async def count_by_type_in_window(self, event_type: str, from_ts: datetime, to_ts: datetime) -> int:
        return await self.count(
            Event.event_type == event_type,
            Event.timestamp >= from_ts,
            Event.timestamp <= to_ts,
        )

    async def funnel_counts(self, from_ts: datetime, to_ts: datetime) -> dict[str, int]:
        """Return per-event-type counts for funnel stages in one query."""
        from sqlalchemy import case, func as sqlfunc

        stmt = (
            select(Event.event_type, sqlfunc.count().label("cnt"))
            .where(Event.timestamp >= from_ts, Event.timestamp <= to_ts)
            .group_by(Event.event_type)
        )
        result = await self.session.execute(stmt)
        return {row.event_type: row.cnt for row in result}
