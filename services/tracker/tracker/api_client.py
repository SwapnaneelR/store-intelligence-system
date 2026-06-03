"""
Async HTTP client — pushes events to the FastAPI ingest endpoint.
Uses a small in-memory buffer and flushes in batches for efficiency.
"""

import asyncio
from datetime import datetime
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class ApiClient:
    def __init__(self, base_url: str, batch_size: int = 50, flush_interval: float = 1.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._buffer: list[dict[str, Any]] = []
        self._client: httpx.AsyncClient | None = None
        self._flush_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
        await self._flush()
        if self._client:
            await self._client.aclose()

    def queue_event(
        self,
        event_type: str,
        timestamp: datetime,
        camera_id: str | None = None,
        track_id: str | None = None,
        session_id: str | None = None,
        zone_id: str | None = None,
        group_id: str | None = None,
        person_class: str | None = None,
        confidence: float | None = None,
        bbox: dict | None = None,
        metadata: dict | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "event_type": event_type,
            "timestamp": timestamp.isoformat(),
        }
        if camera_id:   payload["camera_id"]   = camera_id
        if track_id:    payload["track_id"]    = track_id
        if session_id:  payload["session_id"]  = session_id
        if zone_id:     payload["zone_id"]     = zone_id
        if group_id:    payload["group_id"]    = group_id
        if person_class: payload["person_class"] = person_class
        if confidence is not None: payload["confidence"] = confidence
        if bbox:        payload["bbox"]        = bbox
        if metadata:    payload["metadata"]    = metadata

        self._buffer.append(payload)

        if len(self._buffer) >= self.batch_size:
            asyncio.create_task(self._flush())

    async def _flush(self) -> None:
        if not self._buffer or not self._client:
            return
        batch = self._buffer[:]
        self._buffer.clear()
        try:
            resp = await self._client.post(
                "/api/v1/ingest/batch",
                json={"events": batch},
            )
            resp.raise_for_status()
            logger.debug("batch_flushed", count=len(batch))
        except Exception as exc:
            logger.error("batch_flush_error", error=str(exc), count=len(batch))
            # Re-queue on failure (at-least-once)
            self._buffer = batch + self._buffer

    async def _periodic_flush(self) -> None:
        while True:
            await asyncio.sleep(self.flush_interval)
            await self._flush()
