from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import EventServiceDep
from app.schemas.common import CursorPage
from app.schemas.events import EventFilter, EventRead, EventType, PersonClass

router = APIRouter(prefix="/events", tags=["Events"])


@router.get(
    "",
    summary="List events with cursor pagination",
    response_model=CursorPage[EventRead],
)
async def list_events(
    svc: EventServiceDep,
    event_type: Annotated[list[EventType] | None, Query()] = None,
    camera_id: str | None = None,
    zone_id: str | None = None,
    session_id: str | None = None,
    person_class: PersonClass | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    cursor: str | None = None,
) -> CursorPage[EventRead]:
    filters = EventFilter(
        event_type=event_type,
        camera_id=camera_id,
        zone_id=zone_id,
        session_id=session_id,
        person_class=person_class,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        cursor=cursor,
    )
    return await svc.list_events(filters)
