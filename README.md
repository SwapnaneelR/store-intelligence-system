# Store Intelligence System

> **AI-powered retail analytics platform** — converts CCTV footage into real-time visitor tracking, business KPIs, anomaly detection, and a live operations dashboard.

**Purplle · Brigade Road, Bangalore · Assessment Submission**

---

## Index

### This File
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Services](#services)
- [API Reference](#api-reference)
- [Dashboard Pages](#dashboard-pages)
- [Make Commands](#make-commands)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

### Documentation
| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 11 system design diagrams — C4, ERD, sequence, data flow, deployment |
| [DESIGN.md](DESIGN.md) | Full architecture, API contract, database schema, scalability notes |
| [CHOICES.md](CHOICES.md) | 11 technology decisions with alternatives considered and trade-offs |
| [scripts/youtube_script.md](scripts/youtube_script.md) | YouTube video script — title, description, timestamps, B-roll guide |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/SwapnaneelR/store-intelligence-system.git
cd store-intelligence-system

# 2. Copy env (defaults work out of the box)
cp .env.example .env

# 3. Start everything
docker compose up --build -d

# 4. Seed demo data (optional — populate dashboard without running CV)
make seed-layout   # 5 cameras + 20 store zones
make seed-demo     # synthetic hourly footfall + anomalies
# OR load real POS data:
make seed-csv      # Brigade Road 10-Apr-2026 transaction data

# 5. Open
#    Dashboard  →  http://localhost:3000
#    API Docs   →  http://localhost:8000/docs
#    Swagger    →  http://localhost:8000/redoc
```

> **Prerequisites:** Docker 24+, Docker Compose v2, 8 GB RAM minimum.

---

## Architecture

### Container Overview

```mermaid
C4Container
    title Store Intelligence — Containers

    Person(user, "Store Manager", "Monitors KPIs, anomalies, funnel on dashboard")

    Container_Boundary(docker, "Docker Compose — store-net") {
        Container(tracker,  "Tracker Service",   "Python 3.11",       "YOLOv11n + ByteTrack + Zone/Event engine. Reads MP4/RTSP, batches events to API")
        Container(api,      "FastAPI API",        "Python / FastAPI",  "REST + WebSocket. 12 endpoints. Business metrics, anomaly detection")
        Container(frontend, "Next.js Dashboard",  "Next.js 14 / TS",  "4-page SPA: Dashboard / Events / Anomalies / Funnel")
        ContainerDb(pg,     "PostgreSQL 16",       "Relational DB",    "Events · Sessions · Zones · Anomalies")
        ContainerDb(redis,  "Redis 7",             "In-memory store",  "Pubsub channel store:events for WebSocket fan-out")
    }

    Rel(user,     frontend, "HTTPS :3000",          "Browser")
    Rel(frontend, api,      "REST + WebSocket",      "HTTP :8000 / ws://")
    Rel(tracker,  api,      "POST /ingest/batch",    "HTTP :8000")
    Rel(api,      pg,       "SQL queries",           "asyncpg :5432")
    Rel(api,      redis,    "PUBLISH / SUBSCRIBE",   "redis-py :6379")
```

### Data Flow: CCTV → Dashboard KPI

```mermaid
flowchart LR
    subgraph INPUT["Raw Inputs"]
        V["5× CCTV\nMP4 / RTSP"]
        C["POS CSV\n101 transactions"]
    end

    subgraph CV["Tracker Service"]
        DET["YOLOv11n\nPerson Detection"]
        TRK["ByteTrack\nStable track_id"]
        ZON["ZoneEngine\nShapely polygons"]
        FSM["EventEngine FSM\nNEW → ACTIVE\n→ DWELL → EXITED"]
        ANO["AnomalyRules\nCrowd/LongStay\nReentry/CamFail"]
    end

    subgraph STORE["PostgreSQL"]
        EV[("events")]
        SE[("sessions")]
        AN[("anomalies")]
    end

    subgraph API_["FastAPI"]
        REST["REST KPIs\n/store-metrics/*\n/funnel\n/anomalies"]
        WS["WebSocket\n/ws/events\nRedis pubsub"]
    end

    subgraph DASH["Dashboard"]
        D1["KPI Cards\nOccupancy/Dwell\nPeak Hour"]
        D2["Live Feed\nWS events"]
        D3["Funnel\nConversion"]
    end

    V --> DET --> TRK --> ZON --> FSM
    C -->|"seed_from_csv.py"| EV
    FSM --> ANO
    FSM & ANO -->|"POST /ingest/batch"| EV & SE & AN
    FSM -->|"PUBLISH store:events"| WS
    EV & SE --> REST
    REST --> D1 & D3
    WS --> D2
```

Full architecture detail (11 diagrams): **[ARCHITECTURE.md](ARCHITECTURE.md)**

---

## Services

| Service | URL | Description |
|---|---|---|
| **Dashboard** | http://localhost:3000 | Next.js live analytics dashboard |
| **API** | http://localhost:8000 | FastAPI backend |
| **API Docs** | http://localhost:8000/docs | Swagger UI |
| **Prometheus** | http://localhost:8000/metrics | Metrics scrape endpoint |
| **PostgreSQL** | localhost:5432 | Event + session store |
| **Redis** | localhost:6379 | WebSocket pubsub bus |

```bash
# Optional dev tools (pgAdmin + Redis Commander)
docker compose --profile tools up -d
# pgAdmin          →  http://localhost:5050  (admin@store.local / admin)
# Redis Commander  →  http://localhost:8081
```

---

## API Reference

### Health & Observability

```
GET /health
→ { status, uptime_seconds, checks: { postgres } }

GET /metrics
→ Prometheus text (http_requests_total, request_duration_seconds,
                   store_active_tracks, store_open_anomalies)
```

### Store Metrics (Business KPIs)

```
GET /api/v1/store-metrics/summary
→ {
    total_visitors_today, current_occupancy, unique_visitors_today,
    avg_dwell_seconds, peak_hour, peak_hour_count,
    reentry_rate_pct, group_entry_count, staff_count,
    conversion_rate_pct, total_transactions, total_gmv
  }

GET /api/v1/store-metrics/peak-hours?date=YYYY-MM-DD
→ { date, buckets: [{ hour, count }] }

GET /api/v1/store-metrics/zones?from_ts=&to_ts=
→ [{ zone_id, zone_name, visit_count, avg_dwell_seconds }]
```

### Events

```
GET /api/v1/events
    ?event_type=ENTRY|EXIT|ZONE_ENTER|ZONE_EXIT|DWELL_STARTED|
               DWELL_ENDED|GROUP_ENTRY|STAFF_DETECTED|ANOMALY
    &camera_id=&zone_id=&person_class=customer|staff
    &from_ts=&to_ts=&limit=50&cursor=
→ { items: Event[], next_cursor }
```

### Funnel

```
GET /api/v1/funnel?from_ts=&to_ts=
→ {
    stages: [
      { stage: "Entered Store",  count, drop_off, conversion_rate },
      { stage: "Visited Zone",   count, drop_off, conversion_rate },
      { stage: "Dwelled",        count, drop_off, conversion_rate },
      { stage: "Exited Store",   count, drop_off, conversion_rate }
    ]
  }
```

### Anomalies

```
GET   /api/v1/anomalies?resolved=false&severity=LOW|MEDIUM|HIGH|CRITICAL
PATCH /api/v1/anomalies/{id}/resolve
      body: { resolved_by, notes? }
```

### Event Ingest (for Tracker / Evaluators)

```
POST /api/v1/ingest/event          Single event (internal format)
POST /api/v1/ingest/batch          Up to 500 events per call
POST /api/v1/ingest/footfall-event Organizer-compatible format:
     {
       "event_type":      "entry",       ← lowercase, auto-uppercased
       "id_token":        "ID_60001",    ← maps to track_id
       "store_code":      "store_1076",
       "camera_id":       "cam1",
       "event_timestamp": "2026-03-08T18:10:05Z",  ← maps to timestamp
       "is_staff":        false,         ← maps to person_class
       "gender_pred":     "F",
       "age_pred":        28,
       "age_bucket":      "25-34",
       "is_face_hidden":  false,
       "group_id":        null,
       "group_size":      null
     }
```

### WebSocket

```
WS /ws/events
← { id, event_type, timestamp, track_id, camera_id, zone_id,
    person_class, confidence }
   (real-time push via Redis pubsub; falls back to DB poll if Redis unavailable)
```

---

## Dashboard Pages

| Page | Route | Content |
|---|---|---|
| **Dashboard** | `/dashboard` | 8 KPI cards · hourly footfall BarChart · WS live event feed |
| **Events** | `/events` | Filterable table · event_type + person_class · 5s refresh |
| **Anomalies** | `/anomalies` | Severity summary · resolve workflow · 10s refresh |
| **Funnel** | `/funnel` | ENTRY→ZONE→DWELL→EXIT · drop-off analysis · stage breakdown |

---

## Make Commands

```bash
make up          # Build + start all services (detached)
make down        # Stop (keep volumes)
make reset       # Destroy volumes + rebuild from scratch
make logs        # Tail all service logs
make ps          # Container status
make tools       # Add pgAdmin + Redis Commander
make test        # Run 26 unit tests (no DB required)

# Data seeding
make seed-layout # 5 cameras + 20 brand zones (parse store layout Excel)
make seed-csv    # POS CSV → ENTRY/EXIT/ZONE_ENTER events (101 transactions)
make seed-demo   # Synthetic hourly footfall for 2026-04-10 + 5 anomalies
make demo        # Full stack: up + seed-layout + seed-demo
```

---

## Project Structure

```
store-intelligence-system/
├── dataset/                        Input data (CCTV excluded from git)
│   ├── Brigade Road - Store layout.xlsx
│   ├── Brigade_Bangalore_10_April_26.csv
│   └── Assessment Evaluation Framework.pdf
│
├── services/
│   ├── api/                        FastAPI backend
│   │   ├── app/
│   │   │   ├── routers/            health · metrics · events · anomalies
│   │   │   │                       funnel · store_metrics · ingest · ws_events
│   │   │   ├── services/           EventService · AnomalyService
│   │   │   │                       AnalyticsService · MetricsService
│   │   │   ├── repositories/       EventRepo · AnomalyRepo · MetricsRepo
│   │   │   ├── schemas/            Pydantic v2: events · anomalies · analytics
│   │   │   │                       ingest · common
│   │   │   ├── db/                 SQLAlchemy 2 models + session factory
│   │   │   ├── middleware/         RequestID · error handler
│   │   │   └── redis_client.py     Pubsub singleton + publish helper
│   │   ├── alembic/                Schema migrations
│   │   ├── tests/                  26 tests (pytest-asyncio, mocked deps)
│   │   └── Dockerfile
│   │
│   └── tracker/                    CV pipeline service
│       ├── tracker/
│       │   ├── main.py             Orchestrates 5 cameras concurrently
│       │   ├── ingestor.py         VideoIngestor (MP4/RTSP → frames)
│       │   ├── detector.py         YOLOv11n + ByteTrack wrapper
│       │   ├── zone_engine.py      Shapely point-in-polygon
│       │   ├── event_engine.py     TrackFSM + business event emission
│       │   ├── anomaly_rules.py    CROWD_SURGE · LONG_STAY · EXCESS_REENTRY
│       │   │                       CAMERA_FAILURE rule engine
│       │   ├── api_client.py       Async batch HTTP push to ingest endpoint
│       │   └── config.py           Pydantic settings
│       └── Dockerfile
│
├── frontend/                       Next.js 14 dashboard
│   ├── app/                        App Router pages
│   │   ├── dashboard/              DashboardContent.tsx
│   │   ├── events/                 EventsContent.tsx
│   │   ├── anomalies/              AnomaliesContent.tsx
│   │   └── funnel/                 FunnelContent.tsx
│   ├── components/
│   │   ├── ui/                     shadcn-style: Card · Badge · Button
│   │   │                           Skeleton · Table · Select
│   │   └── layout/                 Sidebar · Header
│   ├── hooks/                      useApi · useWebSocket · useAutoRefresh
│   ├── lib/                        api.ts · utils.ts
│   └── Dockerfile
│
├── scripts/
│   ├── parse_layout.py             Seed cameras + zones from Excel analysis
│   ├── seed_from_csv.py            POS CSV → event rows
│   ├── seed_demo.py                Synthetic demo data (no CV required)
│   └── generate_ppt.py            Generate presentation deck (python-pptx)
│
├── docker-compose.yml              6-service orchestration
├── Makefile                        Dev shortcuts
├── .env.example                    Config template (copy to .env)
├── ARCHITECTURE.md                 11 system design diagrams (Mermaid)
├── DESIGN.md                       Detailed design document
└── CHOICES.md                      Technology decisions + trade-offs
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@postgres:5432/store_intelligence` | PostgreSQL DSN |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` |
| `LOG_FORMAT` | `json` | `json` (prod) or `console` (dev) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | API base URL (browser) |
| `DWELL_THRESHOLD_SECONDS` | `10` | Seconds stationary → DWELL_STARTED |

---

## Troubleshooting

**Services not starting**
```bash
docker compose ps            # which service failed?
docker compose logs api      # check specific service
```

**Migrations failed**
```bash
docker compose logs migrator
make reset                   # wipe DB and retry
```

**Frontend can't reach API**
```bash
# Confirm API healthy:
curl http://localhost:8000/health
# Check NEXT_PUBLIC_API_URL in .env
```

**Dashboard shows no data**
```bash
make seed-demo               # fastest: synthetic data, no CV needed
# or run tracker against CCTV files:
docker compose up tracker
```

---

## Testing

```bash
make test
# ✓ 26 passed in 4.99s
# Covers: health · events · funnel · anomalies · ingest · store-metrics
# All tests use mocked dependencies — no running database required
```

---

## Documentation

| File | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 11 system design diagrams (C4, ERD, sequence, deployment, data flow) |
| [DESIGN.md](DESIGN.md) | Detailed architecture, API contract, database schema, scalability |
| [CHOICES.md](CHOICES.md) | Technology decisions and trade-offs with alternatives considered |
