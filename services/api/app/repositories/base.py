from typing import Any, Generic, TypeVar

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, id: str) -> ModelT | None:
        return await self.session.get(self.model, id)

    async def save(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def count(self, *where_clauses: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        if where_clauses:
            stmt = stmt.where(*where_clauses)
        result = await self.session.execute(stmt)
        return result.scalar_one()
