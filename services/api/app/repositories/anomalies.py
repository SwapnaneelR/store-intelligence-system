import base64
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anomaly
from app.repositories.base import BaseRepository
from app.schemas.anomalies import AnomalyFilter


def _encode_cursor(anomaly_id: str, detected_at: datetime) -> str:
    raw = f"{detected_at.isoformat()}|{anomaly_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    ts_str, anomaly_id = raw.split("|", 1)
    return datetime.fromisoformat(ts_str), anomaly_id


class AnomalyRepository(BaseRepository[Anomaly]):
    model = Anomaly

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_anomalies(self, filters: AnomalyFilter) -> tuple[list[Anomaly], str | None]:
        conditions: list[Any] = []

        if filters.resolved is not None:
            conditions.append(Anomaly.resolved == filters.resolved)
        if filters.severity:
            conditions.append(Anomaly.severity == filters.severity.value)
        if filters.anomaly_type:
            conditions.append(Anomaly.anomaly_type == filters.anomaly_type.value)
        if filters.from_ts:
            conditions.append(Anomaly.detected_at >= filters.from_ts)
        if filters.to_ts:
            conditions.append(Anomaly.detected_at <= filters.to_ts)

        if filters.cursor:
            cursor_ts, cursor_id = _decode_cursor(filters.cursor)
            conditions.append(Anomaly.detected_at <= cursor_ts)
            conditions.append(Anomaly.id < cursor_id)

        stmt = (
            select(Anomaly)
            .where(*conditions)
            .order_by(Anomaly.detected_at.desc(), Anomaly.id.desc())
            .limit(filters.limit + 1)
        )

        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor: str | None = None
        if len(rows) > filters.limit:
            rows = rows[: filters.limit]
            last = rows[-1]
            next_cursor = _encode_cursor(last.id, last.detected_at)

        return rows, next_cursor

    async def count_open(self) -> int:
        return await self.count(Anomaly.resolved == False)  # noqa: E712

    async def resolve(self, anomaly: Anomaly, resolved_by: str, notes: str | None) -> Anomaly:
        anomaly.resolved = True
        anomaly.resolved_at = datetime.utcnow()
        anomaly.resolved_by = resolved_by
        anomaly.notes = notes
        self.session.add(anomaly)
        await self.session.flush()
        await self.session.refresh(anomaly)
        return anomaly
