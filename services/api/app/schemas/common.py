from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    next_cursor: str | None = None
    total: int | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    request_id: str
    errors: list[ErrorDetail]


class BBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    cursor: str | None = None
