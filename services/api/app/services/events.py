import structlog

from app.repositories.events import EventRepository
from app.schemas.common import CursorPage
from app.schemas.events import EventFilter, EventRead

logger = structlog.get_logger(__name__)


class EventService:
    def __init__(self, repo: EventRepository) -> None:
        self.repo = repo

    async def list_events(self, filters: EventFilter) -> CursorPage[EventRead]:
        logger.debug("list_events", filters=filters.model_dump(exclude_none=True))
        rows, next_cursor = await self.repo.list_events(filters)
        items = [EventRead.model_validate(row) for row in rows]
        return CursorPage(items=items, next_cursor=next_cursor)
