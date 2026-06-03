"""Unit tests for GET /api/v1/store-metrics/* endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.analytics import (
    HourBucket,
    PeakHoursResponse,
    StoreMetricsSummary,
    ZonePopularity,
)


def _make_summary(**kwargs) -> StoreMetricsSummary:
    defaults = dict(
        as_of=datetime(2026, 4, 10, 18, 0, 0, tzinfo=timezone.utc),
        total_visitors_today=120,
        current_occupancy=15,
        unique_visitors_today=108,
        avg_dwell_seconds=480.0,
        peak_hour=17,
        peak_hour_count=35,
        reentry_rate_pct=10.0,
        group_entry_count=8,
        staff_count=5,
        conversion_rate_pct=42.5,
        total_transactions=51,
        total_gmv=85000.0,
    )
    defaults.update(kwargs)
    return StoreMetricsSummary(**defaults)


@pytest.mark.asyncio
async def test_store_metrics_summary_ok(client):
    from app.dependencies import get_metrics_service
    from app.main import app
    from app.services.metrics import MetricsService

    mock_svc = AsyncMock(spec=MetricsService)
    mock_svc.get_summary = AsyncMock(return_value=_make_summary())
    app.dependency_overrides[get_metrics_service] = lambda: mock_svc

    response = await client.get("/api/v1/store-metrics/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_visitors_today"] == 120
    assert body["current_occupancy"] == 15
    assert body["peak_hour"] == 17
    assert body["conversion_rate_pct"] == 42.5
    assert body["total_transactions"] == 51
    assert body["total_gmv"] == 85000.0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_store_metrics_summary_zero_visitors(client):
    from app.dependencies import get_metrics_service
    from app.main import app
    from app.services.metrics import MetricsService

    mock_svc = AsyncMock(spec=MetricsService)
    mock_svc.get_summary = AsyncMock(return_value=_make_summary(
        total_visitors_today=0,
        current_occupancy=0,
        unique_visitors_today=0,
        avg_dwell_seconds=0.0,
        peak_hour=None,
        peak_hour_count=0,
        reentry_rate_pct=0.0,
        conversion_rate_pct=0.0,
        total_transactions=0,
        total_gmv=0.0,
    ))
    app.dependency_overrides[get_metrics_service] = lambda: mock_svc

    response = await client.get("/api/v1/store-metrics/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_visitors_today"] == 0
    assert body["peak_hour"] is None
    assert body["conversion_rate_pct"] == 0.0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_peak_hours_today(client):
    from app.dependencies import get_metrics_service
    from app.main import app
    from app.services.metrics import MetricsService

    buckets = [HourBucket(hour=h, count=c) for h, c in [(10, 5), (11, 12), (17, 35)]]
    mock_svc = AsyncMock(spec=MetricsService)
    mock_svc.get_peak_hours = AsyncMock(
        return_value=PeakHoursResponse(date="2026-04-10", buckets=buckets)
    )
    app.dependency_overrides[get_metrics_service] = lambda: mock_svc

    response = await client.get("/api/v1/store-metrics/peak-hours")
    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-04-10"
    assert len(body["buckets"]) == 3
    assert body["buckets"][2]["hour"] == 17
    assert body["buckets"][2]["count"] == 35

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_peak_hours_with_date_param(client):
    from app.dependencies import get_metrics_service
    from app.main import app
    from app.services.metrics import MetricsService

    mock_svc = AsyncMock(spec=MetricsService)
    mock_svc.get_peak_hours = AsyncMock(
        return_value=PeakHoursResponse(date="2026-04-09", buckets=[])
    )
    app.dependency_overrides[get_metrics_service] = lambda: mock_svc

    response = await client.get("/api/v1/store-metrics/peak-hours?date=2026-04-09")
    assert response.status_code == 200
    mock_svc.get_peak_hours.assert_called_once_with("2026-04-09")

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_zone_popularity(client):
    from app.dependencies import get_metrics_service
    from app.main import app
    from app.services.metrics import MetricsService

    zones = [
        ZonePopularity(zone_id="zone_makeup_row", zone_name="Makeup Row", visit_count=45, avg_dwell_seconds=120.0),
        ZonePopularity(zone_id="zone_skincare_row", zone_name="Skincare Row", visit_count=30, avg_dwell_seconds=90.0),
    ]
    mock_svc = AsyncMock(spec=MetricsService)
    mock_svc.get_zone_popularity = AsyncMock(return_value=zones)
    app.dependency_overrides[get_metrics_service] = lambda: mock_svc

    response = await client.get("/api/v1/store-metrics/zones")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["zone_name"] == "Makeup Row"
    assert body[0]["visit_count"] == 45

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_zone_popularity_empty(client):
    from app.dependencies import get_metrics_service
    from app.main import app
    from app.services.metrics import MetricsService

    mock_svc = AsyncMock(spec=MetricsService)
    mock_svc.get_zone_popularity = AsyncMock(return_value=[])
    app.dependency_overrides[get_metrics_service] = lambda: mock_svc

    response = await client.get("/api/v1/store-metrics/zones")
    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides.clear()
