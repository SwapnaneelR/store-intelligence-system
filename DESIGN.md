# Store Intelligence System — Design Document

> **Scope:** Single-store deployment. Scales to multi-store with changes noted in §6.
> Full visual diagrams (C4, ERD, sequence, deployment): **[ARCHITECTURE.md](ARCHITECTURE.md)**

---

## 1. Architecture

### 1.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                                     │
│                                                                         │
│   5× CCTV MP4 / RTSP Streams          POS Transaction CSV              │
│   (CAM 1–5, Brigade Road store)        (ground-truth for conversion)    │
└───────────────────────┬─────────────────────────┬───────────────────────┘
                        │                         │
                        ▼                         ▼ (seed script)
┌───────────────────────────────────┐  ┌──────────────────────────────────┐
│       TRACKER SERVICE             │  │   FastAPI Ingest Endpoint        │
│                                   │  │                                  │
│  VideoIngestor                    │  │  POST /api/v1/ingest/batch       │
│     └─► YOLOv11n (person detect)  │  │  POST /api/v1/ingest/event       │
│          └─► ByteTrack (track_id) │  │  POST /api/v1/ingest/footfall-   │
│               └─► ZoneEngine      │  │       event (organizer format)   │
│                    └─► EventFSM   │──┤                                  │
│                         └─► Anomaly Rules                               │
│                                   │  │  → INSERT events, sessions       │
│  ApiClient (async batch push) ────┘  │  → PUBLISH store:events (Redis)  │
└───────────────────────────────────┘  └──────────────────────────────────┘
                                                        │
                        ┌───────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                    │
│                                                                       │
│   PostgreSQL 16                      Redis 7                         │
│   ├── events (central fact table)    └── store:events (pubsub)       │
│   ├── sessions (one per visit)            consumed by /ws/events     │
│   ├── anomalies                                                       │
│   ├── zones (20 store polygons)                                       │
│   ├── cameras (5 devices)                                             │
│   └── store_layouts                                                   │
└───────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        API LAYER (FastAPI)                            │
│                                                                       │
│  REST  GET /api/v1/store-metrics/summary  → StoreMetricsSummary      │
│        GET /api/v1/store-metrics/peak-hours → hourly footfall        │
│        GET /api/v1/store-metrics/zones      → zone popularity        │
│        GET /api/v1/events                  → paginated event feed    │
│        GET /api/v1/anomalies               → unresolved alerts       │
│        GET /api/v1/funnel                  → conversion funnel       │
│        GET /health  GET /metrics (Prometheus)                        │
│                                                                       │
│  WebSocket  WS /ws/events                                            │
│        Primary path:  Redis SUBSCRIBE store:events → push to clients │
│        Fallback path: DB poll every 3s  (when Redis unavailable)     │
└───────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js 14)                             │
│                                                                       │
│  /dashboard   8 KPI cards · hourly BarChart · WS live event feed     │
│  /events      filterable table · event_type + person_class filters   │
│  /anomalies   severity summary · resolve button                      │
│  /funnel      ENTRY→ZONE→DWELL→EXIT · drop-off analysis              │
└───────────────────────────────────────────────────────────────────────┘
```

### 1.2 Service Boundaries

| Service | Language | Role | State |
|---|---|---|---|
| `tracker` | Python 3.11 | CV pipeline — detect, track, emit events | Stateful (TrackFSM in-process) |
| `api` | Python / FastAPI | REST + WebSocket + analytics | Stateless |
| `frontend` | Node.js / Next.js 14 | Dashboard SPA | Stateless |
| `postgres` | PostgreSQL 16 | Durable event + session store | Durable |
| `redis` | Redis 7 | WebSocket pubsub + cache | Ephemeral |
| `migrator` | Python / Alembic | Schema migration (one-shot, exits) | n/a |

### 1.3 Key Design Decisions vs. Original Plan

| Original Plan | Actual Implementation | Reason |
|---|---|---|
| Separate ingestor + detector + event-engine services | Single unified `tracker` service | Avoids Redis frame streaming overhead for assessment; simpler Docker setup |
| Frame data flows through Redis Streams | Tracker pushes events directly via HTTP POST | Eliminates 30fps × 5 camera Redis writes (~150 msgs/s); events-only is sufficient |
| Redis Streams for event fan-out | Redis pubsub channel `store:events` | Simpler for broadcast; no consumer group coordination needed for WS fan-out |

---

## 2. Data Flow

### 2.1 Frame → Event Pipeline (Tracker)

```
MP4 file / RTSP stream
    │
    │  [every 3rd frame — configurable via PROCESS_EVERY_N_FRAMES]
    ▼
VideoIngestor.frames() → (np.ndarray, frame_w, frame_h, frame_number)
    │
    ▼
Detector.detect_and_track(frame)
    │  YOLOv11n: class=0 (person), conf=0.35, iou=0.45
    │  ByteTrack: persist=True → stable track_id across frames
    │  Staff heuristic: bbox aspect ratio > 3.0 → person_class=staff
    ▼
[{track_id, bbox:{x,y,w,h}, confidence, person_class}, ...]
    │
    ▼
EventEngine.update(detections, frame_w, frame_h, timestamp)
    │  ZoneEngine: normalise bbox to [0,1] coords → point-in-polygon
    │  TrackFSM per track_id: NEW → ACTIVE → DWELL → EXITED
    │  Zone transitions: ZONE_ENTER / ZONE_EXIT events
    │  Dwell: stationary > dwell_threshold_s → DWELL_STARTED
    │  GROUP_ENTRY: detected when group_id set
    ▼
AnomalyRulesEngine.run(engine, timestamp)
    │  CROWD_SURGE:    occupancy > 2× rolling mean  → ANOMALY event
    │  LONG_STAY:      track age > 1800s             → ANOMALY event
    │  EXCESS_REENTRY: reentry_count ≥ 3             → ANOMALY event
    │  CAMERA_FAILURE: no detections > 30s           → ANOMALY event
    ▼
ApiClient.queue_event() → buffer → flush every 1s
    │  POST /api/v1/ingest/batch  [{event_type, timestamp, ...}, ...]
    ▼
FastAPI: INSERT events + sessions → PostgreSQL
         PUBLISH {event_json} → Redis store:events channel
```

### 2.2 Zone Crossing Detection

Zone polygons are stored in normalised `[0,1]` coordinates relative to the camera frame (not pixel coordinates). This makes zones camera-resolution-independent.

On each track update:
1. Compute bottom-centre of bounding box: `(cx, cy) = ((x + w/2) / frame_w, (y + h) / frame_h)`
2. Test `zone.polygon.contains(Point(cx, cy))` for all zones via Shapely
3. Compare result with previous frame's zone membership
4. Emit `ZONE_ENTER` on `not_in → in`, `ZONE_EXIT` on `in → not_in`

### 2.3 Session Lifecycle

```
track_id first appears in entrance zone (or no zone if uncalibrated)
    → INSERT sessions (entered_at, person_class)
    → Emit ENTRY event

track_id disappears from all frames
    → EventEngine._on_track_lost()
    → UPDATE sessions SET exited_at = timestamp
    → Emit EXIT event

dwell detected (stationary > threshold)
    → TrackFSM state = DWELL
    → Emit DWELL_STARTED event
    → On movement resumes: Emit DWELL_ENDED, state = ACTIVE
```

### 2.4 Conversion Rate Calculation

Conversion = unique buyers / total visitors × 100.

Buyers are identified from POS-seeded events: `ZONE_ENTER` events where `metadata->>'order_id' IS NOT NULL`. This links the POS transaction CSV to the event stream without a separate transactions table.

---

## 3. APIs

### 3.1 REST — `/api/v1`

All list endpoints use **base64-encoded cursor pagination** on `(timestamp, id)`. No OFFSET degradation at scale.

```
GET  /health
     → { status: "ok"|"degraded", uptime_seconds, checks: { postgres } }

GET  /metrics
     → Prometheus text format (http_requests_total, request_duration_seconds,
                               store_active_tracks, store_open_anomalies,
                               store_events_ingested_total)

GET  /api/v1/store-metrics/summary
     → StoreMetricsSummary {
         as_of, total_visitors_today, current_occupancy, unique_visitors_today,
         avg_dwell_seconds, peak_hour, peak_hour_count, reentry_rate_pct,
         group_entry_count, staff_count, conversion_rate_pct,
         total_transactions, total_gmv
       }

GET  /api/v1/store-metrics/peak-hours?date=YYYY-MM-DD
     → { date, buckets: [{ hour: 0-23, count }] }

GET  /api/v1/store-metrics/zones?from_ts=&to_ts=
     → [{ zone_id, zone_name, visit_count, avg_dwell_seconds }]
       (zone_name resolved via LEFT JOIN zones table)

GET  /api/v1/events?event_type=&camera_id=&zone_id=&person_class=
                   &from_ts=&to_ts=&limit=50&cursor=
     → CursorPage<EventRead>

GET  /api/v1/anomalies?resolved=false&severity=&anomaly_type=&limit=&cursor=
     → CursorPage<AnomalyRead>

PATCH /api/v1/anomalies/{id}/resolve
     body: { resolved_by: str, notes?: str }
     → AnomalyRead

GET  /api/v1/funnel?from_ts=&to_ts=
     → FunnelResponse {
         stages: [
           { stage: "Entered Store",  count, drop_off, conversion_rate },
           { stage: "Visited Zone",   count, drop_off, conversion_rate },
           { stage: "Dwelled",        count, drop_off, conversion_rate },
           { stage: "Exited Store",   count, drop_off, conversion_rate }
         ]
       }

POST /api/v1/ingest/event        → EventIngestResponse
POST /api/v1/ingest/batch        → BatchIngestResponse { inserted, ids }
POST /api/v1/ingest/footfall-event → FootfallEventResponse
     (organizer format: lowercase event_type, id_token, event_timestamp, is_staff)
```

### 3.2 WebSocket — `/ws/events`

```
WS /ws/events
    ← Initial: { "type": "connected", "channel": "events" }
    ← Per event: {
        id, event_type, timestamp, track_id, camera_id,
        zone_id, person_class, confidence
      }

Primary:  Redis SUBSCRIBE store:events → push each message to all WS clients
Fallback: DB poll every 3s for events since last check (when Redis unavailable)
Reconnect: client auto-reconnects on close with 3s backoff
```

### 3.3 Error Contract

All 4xx/5xx responses:
```json
{
  "request_id": "uuid",
  "errors": [
    { "code": "VALIDATION_ERROR", "message": "...", "field": "event_type" }
  ]
}
```

---

## 4. Event Schema

```json
{
  "id":           "hex-32",
  "event_type":   "ENTRY|EXIT|ZONE_ENTER|ZONE_EXIT|STAFF_DETECTED|GROUP_ENTRY|DWELL_STARTED|DWELL_ENDED|ANOMALY",
  "timestamp":    "2026-04-10T17:30:05.120Z",
  "camera_id":    "hex-32 | null",
  "track_id":     "trk-0042 | ID_60001 | csv_9346413680",
  "session_id":   "hex-32 | null",
  "person_class": "customer | staff | unknown",
  "zone_id":      "zone_makeup_row | null",
  "group_id":     "grp-00031 | null",
  "confidence":   0.94,
  "bbox":         { "x": 312, "y": 204, "w": 68, "h": 182 },
  "metadata": {
    "anomaly_type":   "CROWD_SURGE|LONG_STAY|EXCESS_REENTRY|CAMERA_FAILURE|LOITERING",
    "severity":       "LOW|MEDIUM|HIGH|CRITICAL",
    "order_id":       "104363838",
    "gmv":            274.36,
    "brand":          "DERMDOC",
    "source":         "tracker|footfall_api|csv_seed",
    "gender_pred":    "F|M",
    "age_bucket":     "25-34",
    "is_face_hidden": false,
    "group_size":     3
  }
}
```

### Event Trigger Conditions

| Event | Trigger |
|---|---|
| `ENTRY` | Track first detected in entrance zone (or any zone if uncalibrated) |
| `EXIT` | Track disappears; in exit zone or track age-out |
| `ZONE_ENTER` | Track centroid crosses zone polygon boundary (entering) |
| `ZONE_EXIT` | Track centroid crosses zone polygon boundary (leaving) |
| `STAFF_DETECTED` | ENTRY event where person_class = "staff" |
| `GROUP_ENTRY` | group_id set on ENTRY event |
| `DWELL_STARTED` | Track stationary > `dwell_threshold_s` (default 20s) |
| `DWELL_ENDED` | Dwell track resumes movement (displacement > 0.05 normalised) |
| `ANOMALY` | Any anomaly rule triggers; anomaly_type in metadata |

---

## 5. Database Schema

Schema managed by Alembic (`services/api/alembic/versions/001_initial_schema.py`).

Key tables:

```sql
-- Central fact table (append-only, never UPDATE)
CREATE TABLE events (
    id           VARCHAR(32) PRIMARY KEY,
    event_type   VARCHAR(100) NOT NULL,
    timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    camera_id    VARCHAR(32) REFERENCES cameras(id),
    track_id     VARCHAR(255),
    session_id   VARCHAR(32) REFERENCES sessions(id),
    zone_id      VARCHAR(32) REFERENCES zones(id),
    group_id     VARCHAR(255),
    person_class VARCHAR(50),
    confidence   FLOAT,
    bbox         JSONB,
    metadata     JSONB
);
CREATE INDEX idx_events_type_ts   ON events (event_type, timestamp DESC);
CREATE INDEX idx_events_camera_ts ON events (camera_id,  timestamp DESC);
CREATE INDEX idx_events_zone      ON events (zone_id,    timestamp DESC);
CREATE INDEX idx_events_session   ON events (session_id);

-- One row per store visit
CREATE TABLE sessions (
    id            VARCHAR(32) PRIMARY KEY,
    track_id      VARCHAR(255) NOT NULL,
    camera_id     VARCHAR(32) REFERENCES cameras(id),
    person_class  VARCHAR(50) DEFAULT 'customer',
    entered_at    TIMESTAMPTZ NOT NULL,
    exited_at     TIMESTAMPTZ,
    entry_zone_id VARCHAR(32) REFERENCES zones(id),
    exit_zone_id  VARCHAR(32) REFERENCES zones(id),
    metadata      JSONB
);

-- Anomaly log
CREATE TABLE anomalies (
    id           VARCHAR(32) PRIMARY KEY,
    event_id     VARCHAR(32) REFERENCES events(id),
    anomaly_type VARCHAR(100) NOT NULL,
    severity     VARCHAR(50)  NOT NULL,
    resolved     BOOLEAN DEFAULT FALSE,
    resolved_at  TIMESTAMPTZ,
    resolved_by  VARCHAR(255),
    notes        TEXT,
    detected_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Store zones (normalised polygon coords [0,1])
CREATE TABLE zones (
    id        VARCHAR(32) PRIMARY KEY,
    layout_id VARCHAR(32) REFERENCES store_layouts(id),
    camera_id VARCHAR(32) REFERENCES cameras(id),
    name      VARCHAR(255) NOT NULL,
    zone_type VARCHAR(100) NOT NULL,   -- ENTRANCE|EXIT|PRODUCT|WALKWAY
    polygon   JSONB NOT NULL,          -- [[x,y], [x,y], ...]
    color     VARCHAR(50),
    metadata  JSONB
);
```

**Design decisions:**
- `events` is append-only — immutable audit log.
- `sessions` is the unit of business analysis (one customer visit).
- Raw frame-level tracks are **not** persisted — too high frequency (~150 rows/s for 5 cameras at 30fps). Only distilled business events are stored.
- `JSONB metadata` on every table allows new event subtypes without schema migrations.
- Zone polygons use normalised `[0,1]` coordinates to decouple from camera resolution changes.

---

## 6. Scalability

### Current Ceiling (Single Node)

| Layer | Constraint | Ceiling |
|---|---|---|
| Detection | CPU (YOLOv11n) | ~3 cameras at 10fps on modern CPU |
| Detection | GPU (RTX 3080) | ~8+ cameras at 1080p / 10fps |
| Event Engine | Python process per camera group | ~16 cameras (CPU-bound) |
| PostgreSQL | Vertical + connection pool (10+20) | ~5k events/s write |
| Redis | Single node pubsub | ~100k msg/s |
| API | Uvicorn async workers | ~2k req/s REST |

### Horizontal Scale Path

```
Single store (current)            Multi-store / high volume
─────────────────────────────────────────────────────────────────
1 tracker process per 5 cameras → Kubernetes pod per camera group
HTTP batch push to API          → Kafka (durable, multi-consumer)
Redis pubsub                    → Redis Cluster (per-store namespaces)
PostgreSQL single node          → Citus (shard by store_id + date)
API stateless × 1               → API × N behind load balancer
```

### Extension Points for Multi-Store

1. Add `store_id` column on `events`, `sessions`, `anomalies`, `zones`, `cameras`.
2. Partition `events` by `(store_id, timestamp)` range.
3. Redis namespace: `store:{store_id}:events` pubsub channel.
4. Replace HTTP batch push with Kafka for cross-store aggregation.

None of these changes break backward compatibility with the single-store schema.

---

## 7. Observability

### Prometheus Metrics (GET /metrics)

| Metric | Type | Labels |
|---|---|---|
| `http_requests_total` | Counter | method, path, status_code |
| `http_request_duration_seconds` | Histogram | method, path |
| `store_active_tracks` | Gauge | — |
| `store_open_anomalies` | Gauge | — |
| `store_events_ingested_total` | Counter | event_type |

### Structured Logging (structlog)

Every log line includes: `timestamp`, `level`, `logger`, `request_id`, plus event-specific context fields (e.g., `event_type`, `track_id`, `error`). Format: JSON in production (`LOG_FORMAT=json`), human-readable console in dev.

### Health Check

`GET /health` tests `SELECT 1` on PostgreSQL. Returns `200 ok` or `503 degraded`. Used by Docker healthcheck and load balancer.
