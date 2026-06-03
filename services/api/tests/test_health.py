import pytest
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_health_ok(client):
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    from app.db.session import get_db
    from app.main import app

    async def override_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "uptime_seconds" in body
    assert body["checks"]["postgres"] == "ok"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_postgres_fail(client):
    from app.db.session import get_db
    from app.main import app

    async def override_db():
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute = AsyncMock(side_effect=Exception("connection refused"))
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    response = await client.get("/health")
    assert response.status_code == 503
    assert response.json()["checks"]["postgres"] == "error"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_sets_request_id(client):
    from app.db.session import get_db
    from app.main import app

    async def override_db():
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute = AsyncMock()
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    response = await client.get("/health")
    assert "x-request-id" in response.headers

    app.dependency_overrides.clear()
