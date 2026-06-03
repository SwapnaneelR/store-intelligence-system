"""Unit tests for POST /api/v1/ingest/* endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


def _mock_db(session: AsyncMock):
    async def override():
        yield session
    return override


TS = "2026-04-10T17:30:00Z"


@pytest.mark.asyncio
async def test_ingest_single_event(client):
    from app.db.session import get_db
    from app.main import app

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    app.dependency_overrides[get_db] = _mock_db(mock_session)

    with patch("app.routers.ingest.publish_event", new_callable=AsyncMock):
        response = await client.post("/api/v1/ingest/event", json={
            "event_type": "ENTRY",
            "timestamp": TS,
            "camera_id": "cam_1",
            "track_id": "trk_001",
            "person_class": "customer",
            "confidence": 0.92,
        })

    assert response.status_code == 201
    body = response.json()
    assert body["event_type"] == "ENTRY"
    assert "id" in body
    assert "timestamp" in body

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ingest_event_invalid_type(client):
    from app.db.session import get_db
    from app.main import app

    mock_session = AsyncMock(spec=AsyncSession)
    app.dependency_overrides[get_db] = _mock_db(mock_session)

    response = await client.post("/api/v1/ingest/event", json={
        "event_type": "BOGUS_TYPE",
        "timestamp": TS,
    })
    assert response.status_code == 422

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ingest_batch(client):
    from app.db.session import get_db
    from app.main import app

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()
    app.dependency_overrides[get_db] = _mock_db(mock_session)

    events = [
        {"event_type": "ENTRY", "timestamp": TS, "track_id": f"trk_{i}", "person_class": "customer"}
        for i in range(3)
    ]

    with patch("app.routers.ingest.publish_event", new_callable=AsyncMock):
        response = await client.post("/api/v1/ingest/batch", json={"events": events})

    assert response.status_code == 201
    body = response.json()
    assert body["inserted"] == 3
    assert len(body["ids"]) == 3

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ingest_batch_empty_rejected(client):
    response = await client.post("/api/v1/ingest/batch", json={"events": []})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_footfall_event_organizer_format(client):
    """Test organizer-format event: lowercase event_type, id_token, is_staff, demographics."""
    from app.db.session import get_db
    from app.main import app

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()
    app.dependency_overrides[get_db] = _mock_db(mock_session)

    with patch("app.routers.ingest.publish_event", new_callable=AsyncMock):
        response = await client.post("/api/v1/ingest/footfall-event", json={
            "event_type": "entry",          # lowercase — must be accepted
            "id_token": "ID_60001",         # not track_id
            "store_code": "store_1076",
            "camera_id": "cam1",
            "event_timestamp": TS,          # not timestamp
            "is_staff": False,
            "gender_pred": "F",
            "age_pred": 28,
            "age_bucket": "25-34",
            "is_face_hidden": False,
            "group_id": None,
            "group_size": None,
        })

    assert response.status_code == 201
    body = response.json()
    assert body["event_type"] == "ENTRY"   # normalised to uppercase
    assert "id" in body

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ingest_footfall_event_staff(client):
    from app.db.session import get_db
    from app.main import app

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()
    app.dependency_overrides[get_db] = _mock_db(mock_session)

    added_events = []
    original_add = mock_session.add

    def capture_add(obj):
        added_events.append(obj)

    mock_session.add = capture_add

    with patch("app.routers.ingest.publish_event", new_callable=AsyncMock):
        response = await client.post("/api/v1/ingest/footfall-event", json={
            "event_type": "entry",
            "id_token": "STAFF_001",
            "event_timestamp": TS,
            "is_staff": True,
        })

    assert response.status_code == 201
    # The Event added to session should have person_class = "staff"
    assert any(
        getattr(ev, "person_class", None) == "staff"
        for ev in added_events
    )

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ingest_footfall_missing_required(client):
    response = await client.post("/api/v1/ingest/footfall-event", json={
        "event_type": "entry",
        # id_token missing
        "event_timestamp": TS,
    })
    assert response.status_code == 422
