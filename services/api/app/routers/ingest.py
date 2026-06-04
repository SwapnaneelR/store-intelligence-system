import json
import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event
from app.db.models import Session as VisitSession
from app.db.session import get_db
from app.redis_client import publish_event
from app.routers.metrics import events_ingested_total
from app.schemas.events import EventType
from app.schemas.ingest import BatchIngest, BatchIngestResponse, EventIngest, EventIngestResponse

router = APIRouter(prefix="/ingest", tags=["Ingest"])
logger = structlog.get_logger(__name__)


# ── Organizer-compatible schema ────────────────────────────────────────────────
class FootfallEvent(BaseModel):
    event_type: str           # "entry" / "exit" — normalised to uppercase
    id_token: str             # maps to track_id
    store_code: str | None = None
    camera_id: str | None = None
    event_timestamp: datetime  # maps to timestamp
    is_staff: bool = False    # maps to person_class
    gender_pred: str | None = None
    age_pred: int | None = None
    age_bucket: str | None = None
    is_face_hidden: bool = False
    group_id: str | None = None
    group_size: int | None = None


class FootfallEventResponse(BaseModel):
    id: str
    event_type: str
    timestamp: datetime


def _event_to_json(ev: Event) -> str:
    return json.dumps({
        "id": ev.id,
        "event_type": ev.event_type,
        "timestamp": ev.timestamp.isoformat(),
        "track_id": ev.track_id,
        "camera_id": ev.camera_id,
        "zone_id": ev.zone_id,
        "person_class": ev.person_class,
        "confidence": ev.confidence,
    })


async def _sync_session(db: AsyncSession, payload: EventIngest) -> None:
    """Create or update a Session row when ENTRY/EXIT events arrive from the tracker."""
    if not payload.session_id or payload.event_type not in (EventType.ENTRY, EventType.EXIT):
        return

    if payload.event_type == EventType.ENTRY:
        existing = await db.get(VisitSession, payload.session_id)
        if not existing:
            visit = VisitSession(
                id=payload.session_id,
                track_id=payload.track_id or "unknown",
                camera_id=payload.camera_id,
                person_class=(payload.person_class.value if payload.person_class else "customer"),
                entered_at=payload.timestamp,
                entry_zone_id=payload.zone_id,
            )
            db.add(visit)
    elif payload.event_type == EventType.EXIT:
        stmt = (
            update(VisitSession)
            .where(VisitSession.id == payload.session_id)
            .values(exited_at=payload.timestamp, exit_zone_id=payload.zone_id)
        )
        await db.execute(stmt)


async def _write_event(session: AsyncSession, payload: EventIngest) -> Event:
    ev = Event(
        id=uuid.uuid4().hex,
        event_type=payload.event_type.value,
        timestamp=payload.timestamp,
        camera_id=payload.camera_id,
        track_id=payload.track_id,
        session_id=payload.session_id,
        zone_id=payload.zone_id,
        group_id=payload.group_id,
        person_class=payload.person_class.value if payload.person_class else None,
        confidence=payload.confidence,
        bbox=payload.bbox.model_dump() if payload.bbox else None,
        metadata_=payload.metadata,
    )
    session.add(ev)
    events_ingested_total.labels(payload.event_type.value).inc()
    return ev


@router.post(
    "/event",
    summary="Ingest a single event from the tracker",
    response_model=EventIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_event(
    payload: EventIngest,
    session: AsyncSession = Depends(get_db),
) -> EventIngestResponse:
    ev = await _write_event(session, payload)
    await session.commit()
    await publish_event(_event_to_json(ev))
    logger.info("event_ingested", event_type=ev.event_type, track_id=ev.track_id)
    return EventIngestResponse(id=ev.id, event_type=ev.event_type, timestamp=ev.timestamp)


@router.post(
    "/footfall-event",
    summary="Ingest organizer-format footfall event (lowercase event_type, id_token, is_staff)",
    response_model=FootfallEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_footfall_event(
    payload: FootfallEvent,
    session: AsyncSession = Depends(get_db),
) -> FootfallEventResponse:
    event_type = payload.event_type.upper()
    person_class = "staff" if payload.is_staff else "customer"
    meta = {k: v for k, v in {
        "store_code": payload.store_code,
        "gender_pred": payload.gender_pred,
        "age_pred": payload.age_pred,
        "age_bucket": payload.age_bucket,
        "is_face_hidden": payload.is_face_hidden,
        "group_size": payload.group_size,
        "source": "footfall_api",
    }.items() if v is not None}

    ev = Event(
        id=uuid.uuid4().hex,
        event_type=event_type,
        timestamp=payload.event_timestamp,
        camera_id=payload.camera_id,
        track_id=payload.id_token,
        group_id=payload.group_id,
        person_class=person_class,
        confidence=None,
        metadata_=meta,
    )
    session.add(ev)
    events_ingested_total.labels(event_type).inc()
    await session.commit()
    await publish_event(_event_to_json(ev))
    logger.info("footfall_event_ingested", event_type=event_type, track_id=payload.id_token)
    return FootfallEventResponse(id=ev.id, event_type=ev.event_type, timestamp=ev.timestamp)


@router.post(
    "/batch",
    summary="Ingest a batch of events from the tracker",
    response_model=BatchIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_batch(
    payload: BatchIngest,
    session: AsyncSession = Depends(get_db),
) -> BatchIngestResponse:
    events = []
    for item in payload.events:
        ev = await _write_event(session, item)
        await _sync_session(session, item)
        events.append(ev)
    await session.commit()
    for ev in events:
        await publish_event(_event_to_json(ev))
    logger.info("batch_ingested", count=len(events))
    return BatchIngestResponse(inserted=len(events), ids=[e.id for e in events])
