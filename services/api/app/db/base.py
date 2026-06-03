from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column
from sqlalchemy import DateTime, func
from datetime import datetime
import uuid


class Base(DeclarativeBase):
    pass


def uuid_pk() -> MappedColumn:
    return mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))


def now_utc() -> MappedColumn:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
