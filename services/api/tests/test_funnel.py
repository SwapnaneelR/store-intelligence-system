from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.schemas.analytics import FunnelResponse, FunnelStage


def _make_funnel() -> FunnelResponse:
    return FunnelResponse(
        from_ts=datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
        to_ts=datetime(2026, 6, 1, 23, 59, 59, tzinfo=timezone.utc),
        stages=[
            FunnelStage(stage="Entered Store", count=100, drop_off=0, conversion_rate=100.0),
            FunnelStage(stage="Visited Zone", count=80, drop_off=20, conversion_rate=80.0),
            FunnelStage(stage="Dwelled", count=40, drop_off=40, conversion_rate=50.0),
            FunnelStage(stage="Exited Store", count=95, drop_off=5, conversion_rate=95.0),
        ],
    )


@pytest.mark.asyncio
async def test_funnel_returns_stages(client):
    from app.dependencies import get_analytics_service
    from app.main import app
    from app.services.analytics import AnalyticsService

    mock_svc = AsyncMock(spec=AnalyticsService)
    mock_svc.get_funnel = AsyncMock(return_value=_make_funnel())
    app.dependency_overrides[get_analytics_service] = lambda: mock_svc

    response = await client.get("/api/v1/funnel")
    assert response.status_code == 200
    body = response.json()
    assert len(body["stages"]) == 4
    assert body["stages"][0]["stage"] == "Entered Store"
    assert body["stages"][0]["count"] == 100

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_funnel_with_custom_range(client):
    from app.dependencies import get_analytics_service
    from app.main import app
    from app.services.analytics import AnalyticsService

    mock_svc = AsyncMock(spec=AnalyticsService)
    mock_svc.get_funnel = AsyncMock(return_value=_make_funnel())
    app.dependency_overrides[get_analytics_service] = lambda: mock_svc

    response = await client.get(
        "/api/v1/funnel",
        params={"from_ts": "2026-06-01T00:00:00Z", "to_ts": "2026-06-01T12:00:00Z"},
    )
    assert response.status_code == 200
    mock_svc.get_funnel.assert_called_once()

    app.dependency_overrides.clear()
