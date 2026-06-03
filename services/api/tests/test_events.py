from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.common import CursorPage
from app.schemas.events import EventRead


def _make_event(event_type: str = "ENTRY") -> EventRead:
    return EventRead(
        id="abc123",
        event_type=event_type,
        timestamp=datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        camera_id="cam-01",
        track_id="trk-001",
        session_id="sess-001",
        zone_id=None,
        group_id=None,
        person_class="customer",
        confidence=0.95,
        bbox=None,
        metadata_=None,
    )


@pytest.mark.asyncio
async def test_list_events_returns_page(client):
    from app.dependencies import get_event_service
    from app.main import app
    from app.services.events import EventService

    mock_svc = AsyncMock(spec=EventService)
    mock_svc.list_events = AsyncMock(
        return_value=CursorPage(items=[_make_event("ENTRY")], next_cursor=None)
    )
    app.dependency_overrides[get_event_service] = lambda: mock_svc

    response = await client.get("/api/v1/events")
    assert response.status_code == 200
    body = response.json()
    assert body["next_cursor"] is None
    assert len(body["items"]) == 1
    assert body["items"][0]["event_type"] == "ENTRY"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_events_with_type_filter(client):
    from app.dependencies import get_event_service
    from app.main import app
    from app.services.events import EventService

    mock_svc = AsyncMock(spec=EventService)
    mock_svc.list_events = AsyncMock(
        return_value=CursorPage(items=[_make_event("EXIT")], next_cursor=None)
    )
    app.dependency_overrides[get_event_service] = lambda: mock_svc

    response = await client.get("/api/v1/events?event_type=EXIT")
    assert response.status_code == 200
    assert response.json()["items"][0]["event_type"] == "EXIT"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_events_invalid_limit(client):
    from app.dependencies import get_event_service
    from app.main import app
    from app.services.events import EventService

    mock_svc = AsyncMock(spec=EventService)
    app.dependency_overrides[get_event_service] = lambda: mock_svc

    response = await client.get("/api/v1/events?limit=9999")
    assert response.status_code == 422

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_events_cursor_pagination(client):
    from app.dependencies import get_event_service
    from app.main import app
    from app.services.events import EventService

    mock_svc = AsyncMock(spec=EventService)
    mock_svc.list_events = AsyncMock(
        return_value=CursorPage(items=[_make_event()], next_cursor="next-token-abc")
    )
    app.dependency_overrides[get_event_service] = lambda: mock_svc

    response = await client.get("/api/v1/events?limit=1")
    assert response.status_code == 200
    assert response.json()["next_cursor"] == "next-token-abc"

    app.dependency_overrides.clear()
