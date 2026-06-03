import time
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["Health"])
logger = structlog.get_logger(__name__)

_start_time = time.monotonic()


@router.get(
    "/health",
    summary="Liveness + readiness probe",
    response_description="Service health status",
)
async def health(session: Annotated[AsyncSession, Depends(get_db)]) -> JSONResponse:
    checks: dict[str, str] = {}
    overall_ok = True

    try:
        await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        logger.error("health_postgres_fail", error=str(exc))
        checks["postgres"] = "error"
        overall_ok = False

    uptime = round(time.monotonic() - _start_time, 2)
    body = {"status": "ok" if overall_ok else "degraded", "uptime_seconds": uptime, "checks": checks}
    code = status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=body, status_code=code)
