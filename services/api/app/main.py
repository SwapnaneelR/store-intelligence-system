import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.logging_config import configure_logging
from app.middleware.error_handler import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.middleware.request_id import RequestIDMiddleware
from app.redis_client import close_redis, init_redis
from app.routers import (
    anomalies_router,
    events_router,
    funnel_router,
    health_router,
    ingest_router,
    metrics_router,
    store_metrics_router,
)
from app.routers.metrics import http_request_duration_seconds, http_requests_total
from app.routers.ws_events import router as ws_router

settings = get_settings()
configure_logging(settings)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup", app=settings.app_name, version=settings.app_version)
    await init_redis()
    yield
    await close_redis()
    logger.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Store Intelligence API — real-time footfall, event, and anomaly tracking",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# --- Middleware (LIFO: last added = first executed) ---
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception handlers ---
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


# --- Prometheus instrumentation ---
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    path = request.url.path
    http_requests_total.labels(request.method, path, str(response.status_code)).inc()
    http_request_duration_seconds.labels(request.method, path).observe(duration)
    return response


# --- Routers ---
API_PREFIX = "/api/v1"
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(ws_router)                           # ws://.../ws/events
app.include_router(events_router, prefix=API_PREFIX)
app.include_router(anomalies_router, prefix=API_PREFIX)
app.include_router(funnel_router, prefix=API_PREFIX)
app.include_router(ingest_router, prefix=API_PREFIX)
app.include_router(store_metrics_router, prefix=API_PREFIX)
