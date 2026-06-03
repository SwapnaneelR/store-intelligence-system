import structlog
from fastapi import HTTPException, status

from app.repositories.anomalies import AnomalyRepository
from app.schemas.anomalies import AnomalyFilter, AnomalyRead, AnomalyResolve
from app.schemas.common import CursorPage

logger = structlog.get_logger(__name__)


class AnomalyService:
    def __init__(self, repo: AnomalyRepository) -> None:
        self.repo = repo

    async def list_anomalies(self, filters: AnomalyFilter) -> CursorPage[AnomalyRead]:
        logger.debug("list_anomalies", filters=filters.model_dump(exclude_none=True))
        rows, next_cursor = await self.repo.list_anomalies(filters)
        items = [AnomalyRead.model_validate(row) for row in rows]
        return CursorPage(items=items, next_cursor=next_cursor)

    async def resolve_anomaly(self, anomaly_id: str, payload: AnomalyResolve) -> AnomalyRead:
        anomaly = await self.repo.get_by_id(anomaly_id)
        if anomaly is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anomaly not found")
        if anomaly.resolved:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Anomaly already resolved")

        updated = await self.repo.resolve(anomaly, payload.resolved_by, payload.notes)
        logger.info("anomaly_resolved", anomaly_id=anomaly_id, resolved_by=payload.resolved_by)
        return AnomalyRead.model_validate(updated)
