import structlog
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorDetail, ErrorResponse

logger = structlog.get_logger(__name__)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning("http_exception", status_code=exc.status_code, detail=exc.detail)
    body = ErrorResponse(
        request_id=_request_id(request),
        errors=[ErrorDetail(code=f"HTTP_{exc.status_code}", message=str(exc.detail))],
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        ErrorDetail(
            code="VALIDATION_ERROR",
            message=err["msg"],
            field=".".join(str(loc) for loc in err["loc"]),
        )
        for err in exc.errors()
    ]
    logger.warning("validation_error", error_count=len(errors))
    body = ErrorResponse(request_id=_request_id(request), errors=errors)
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body.model_dump())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", exc_info=exc)
    body = ErrorResponse(
        request_id=_request_id(request),
        errors=[ErrorDetail(code="INTERNAL_ERROR", message="An unexpected error occurred")],
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body.model_dump())
