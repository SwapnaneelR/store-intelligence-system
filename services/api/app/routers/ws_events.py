"""
WebSocket /ws/events — real-time event fan-out.

Each connected client receives JSON event payloads as they are ingested.
Events are published via Redis pubsub channel `store:events`.
Falls back to DB polling (every 3s) when Redis is unavailable.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory
from app.redis_client import EVENTS_CHANNEL, get_redis

router = APIRouter(tags=["WebSocket"])
logger = structlog.get_logger(__name__)

POLL_INTERVAL = 3.0  # seconds, fallback DB poll


# ── Redis subscriber path ──────────────────────────────────────────────────────

async def _redis_subscriber(ws: WebSocket) -> None:
    r = get_redis()
    if r is None:
        raise RuntimeError("redis not available")

    pubsub = r.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)
    logger.debug("ws_redis_subscribed")

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await ws.send_text(message["data"])
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        await pubsub.unsubscribe(EVENTS_CHANNEL)
        await pubsub.aclose()


# ── DB polling fallback ────────────────────────────────────────────────────────

async def _db_poller(ws: WebSocket) -> None:
    """Poll DB every POLL_INTERVAL seconds, send new events since last check."""
    from sqlalchemy import select
    from app.db.models import Event

    since = datetime.now(timezone.utc) - timedelta(seconds=10)

    try:
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            async with AsyncSessionFactory() as session:
                stmt = (
                    select(Event)
                    .where(Event.timestamp > since)
                    .order_by(Event.timestamp.asc())
                    .limit(50)
                )
                result = await session.execute(stmt)
                rows = list(result.scalars().all())

            if rows:
                since = rows[-1].timestamp
                for ev in rows:
                    payload = {
                        "id": ev.id,
                        "event_type": ev.event_type,
                        "timestamp": ev.timestamp.isoformat(),
                        "track_id": ev.track_id,
                        "camera_id": ev.camera_id,
                        "zone_id": ev.zone_id,
                        "person_class": ev.person_class,
                        "confidence": ev.confidence,
                    }
                    await ws.send_text(json.dumps(payload))
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("ws_client_connected", client=str(websocket.client))

    # Announce connection
    await websocket.send_text(json.dumps({"type": "connected", "channel": "events"}))

    try:
        if get_redis() is not None:
            await _redis_subscriber(websocket)
        else:
            logger.warning("ws_redis_unavailable_fallback_to_db_poll")
            await _db_poller(websocket)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("ws_error", error=str(exc))
    finally:
        logger.info("ws_client_disconnected", client=str(websocket.client))
