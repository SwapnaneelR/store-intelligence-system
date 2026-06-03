from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.dependencies import AnomalyServiceDep
from app.schemas.anomalies import AnomalyFilter, AnomalyRead, AnomalyResolve, AnomalySeverity, AnomalyType
from app.schemas.common import CursorPage

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.get(
    "",
    summary="List anomalies with cursor pagination",
    response_model=CursorPage[AnomalyRead],
)
async def list_anomalies(
    svc: AnomalyServiceDep,
    resolved: bool | None = False,
    severity: AnomalySeverity | None = None,
    anomaly_type: AnomalyType | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    cursor: str | None = None,
) -> CursorPage[AnomalyRead]:
    filters = AnomalyFilter(
        resolved=resolved,
        severity=severity,
        anomaly_type=anomaly_type,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        cursor=cursor,
    )
    return await svc.list_anomalies(filters)


@router.patch(
    "/{anomaly_id}/resolve",
    summary="Mark anomaly as resolved",
    response_model=AnomalyRead,
    status_code=status.HTTP_200_OK,
)
async def resolve_anomaly(
    anomaly_id: str,
    payload: AnomalyResolve,
    svc: AnomalyServiceDep,
) -> AnomalyRead:
    return await svc.resolve_anomaly(anomaly_id, payload)
