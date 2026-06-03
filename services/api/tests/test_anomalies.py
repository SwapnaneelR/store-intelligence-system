from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.schemas.anomalies import AnomalyRead
from app.schemas.common import CursorPage


def _make_anomaly(resolved: bool = False) -> AnomalyRead:
    return AnomalyRead(
        id="ano-001",
        event_id="evt-001",
        anomaly_type="LOITERING",
        severity="HIGH",
        resolved=resolved,
        resolved_at=None,
        resolved_by=None,
        notes=None,
        detected_at=datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_list_anomalies_unresolved(client):
    from app.dependencies import get_anomaly_service
    from app.main import app
    from app.services.anomalies import AnomalyService

    mock_svc = AsyncMock(spec=AnomalyService)
    mock_svc.list_anomalies = AsyncMock(
        return_value=CursorPage(items=[_make_anomaly()], next_cursor=None)
    )
    app.dependency_overrides[get_anomaly_service] = lambda: mock_svc

    response = await client.get("/api/v1/anomalies")
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["resolved"] is False

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_resolve_anomaly_success(client):
    from app.dependencies import get_anomaly_service
    from app.main import app
    from app.services.anomalies import AnomalyService

    resolved = _make_anomaly(resolved=True)
    mock_svc = AsyncMock(spec=AnomalyService)
    mock_svc.resolve_anomaly = AsyncMock(return_value=resolved)
    app.dependency_overrides[get_anomaly_service] = lambda: mock_svc

    response = await client.patch(
        "/api/v1/anomalies/ano-001/resolve",
        json={"resolved_by": "ops-team", "notes": "false positive"},
    )
    assert response.status_code == 200
    assert response.json()["resolved"] is True

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_resolve_anomaly_not_found(client):
    from app.dependencies import get_anomaly_service
    from app.main import app
    from app.services.anomalies import AnomalyService

    mock_svc = AsyncMock(spec=AnomalyService)
    mock_svc.resolve_anomaly = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Anomaly not found")
    )
    app.dependency_overrides[get_anomaly_service] = lambda: mock_svc

    response = await client.patch(
        "/api/v1/anomalies/no-such-id/resolve",
        json={"resolved_by": "ops-team"},
    )
    assert response.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_resolve_anomaly_missing_resolved_by(client):
    from app.dependencies import get_anomaly_service
    from app.main import app
    from app.services.anomalies import AnomalyService

    mock_svc = AsyncMock(spec=AnomalyService)
    app.dependency_overrides[get_anomaly_service] = lambda: mock_svc

    response = await client.patch("/api/v1/anomalies/ano-001/resolve", json={})
    assert response.status_code == 422

    app.dependency_overrides.clear()
