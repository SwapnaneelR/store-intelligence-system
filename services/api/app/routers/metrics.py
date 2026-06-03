import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

router = APIRouter(tags=["Metrics"])

# --- Prometheus instruments ---
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

active_tracks_gauge = Gauge("store_active_tracks", "Currently tracked persons")
open_anomalies_gauge = Gauge("store_open_anomalies", "Unresolved anomaly count")
events_ingested_total = Counter("store_events_ingested_total", "Events written to DB", ["event_type"])


@router.get(
    "/metrics",
    summary="Prometheus metrics scrape endpoint",
    response_class=PlainTextResponse,
    include_in_schema=False,
)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
