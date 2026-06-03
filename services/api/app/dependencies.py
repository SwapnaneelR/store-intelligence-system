from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.anomalies import AnomalyRepository
from app.repositories.events import EventRepository
from app.repositories.metrics import MetricsRepository
from app.services.analytics import AnalyticsService
from app.services.anomalies import AnomalyService
from app.services.events import EventService
from app.services.metrics import MetricsService


def get_event_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> EventRepository:
    return EventRepository(session)


def get_anomaly_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> AnomalyRepository:
    return AnomalyRepository(session)


def get_metrics_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> MetricsRepository:
    return MetricsRepository(session)


def get_event_service(repo: Annotated[EventRepository, Depends(get_event_repo)]) -> EventService:
    return EventService(repo)


def get_anomaly_service(repo: Annotated[AnomalyRepository, Depends(get_anomaly_repo)]) -> AnomalyService:
    return AnomalyService(repo)


def get_analytics_service(
    event_repo: Annotated[EventRepository, Depends(get_event_repo)],
    anomaly_repo: Annotated[AnomalyRepository, Depends(get_anomaly_repo)],
) -> AnalyticsService:
    return AnalyticsService(event_repo, anomaly_repo)


def get_metrics_service(repo: Annotated[MetricsRepository, Depends(get_metrics_repo)]) -> MetricsService:
    return MetricsService(repo)


EventServiceDep = Annotated[EventService, Depends(get_event_service)]
AnomalyServiceDep = Annotated[AnomalyService, Depends(get_anomaly_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]
MetricsServiceDep = Annotated[MetricsService, Depends(get_metrics_service)]
