# Store Intelligence — System Design Architecture

> **Render these diagrams:** GitHub, Notion, VS Code (Markdown Preview Mermaid Support), or [mermaid.live](https://mermaid.live)

---

## 1. C4 — Context Diagram

```mermaid
C4Context
    title Store Intelligence — System Context

    Person(manager, "Store Manager", "Views real-time footfall KPIs, anomalies, funnel on dashboard")
    Person(ops, "Ops / Evaluator", "Hits REST APIs, checks Prometheus metrics, runs docker compose")

    System(si, "Store Intelligence", "AI-powered retail analytics platform — tracks visitors, generates events, exposes KPIs")

    System_Ext(cctv, "CCTV Cameras (×5)", "H.264 MP4 / RTSP streams from Brigade Road store")
    System_Ext(pos, "POS System", "Transaction CSV — order_id, GMV, salesperson, brand")
    System_Ext(prometheus, "Prometheus / Grafana", "Scrapes /metrics endpoint for observability")

    Rel(cctv,    si,      "Video frames (MP4 / RTSP)")
    Rel(pos,     si,      "CSV seed — ENTRY/EXIT/ZONE_ENTER events")
    Rel(manager, si,      "Views dashboard", "HTTPS / WebSocket")
    Rel(ops,     si,      "REST API calls", "HTTP")
    Rel(si,      prometheus, "Exposes /metrics", "Prometheus text format")
```

---

## 2. C4 — Container Diagram

```mermaid
C4Container
    title Store Intelligence — Containers

    Person(user, "Store Manager")

    Container_Boundary(docker, "Docker Compose Network: store-net") {

        Container(tracker,   "Tracker Service",    "Python 3.11",      "YOLOv11 detection + ByteTrack + Zone/Event engine. Reads MP4, POSTs events to API")
        Container(api,       "FastAPI API",         "Python / FastAPI",  "REST + WebSocket server. 10+ endpoints. Alembic migrations")
        Container(frontend,  "Next.js Dashboard",   "Next.js 14 / TS",  "4-page SPA: Dashboard, Events, Anomalies, Funnel")
        ContainerDb(pg,      "PostgreSQL 16",        "Relational DB",    "Events, Sessions, Zones, Anomalies")
        ContainerDb(redis,   "Redis 7",              "In-memory store",  "Pubsub channel store:events for WS fan-out")
        Container(migrator,  "Alembic Migrator",    "One-shot job",     "Runs migrations on startup, exits")
    }

    Rel(user,     frontend, "HTTPS :3000",     "Browser")
    Rel(frontend, api,      "REST + WebSocket", "HTTP :8000 / WS")
    Rel(tracker,  api,      "POST /api/v1/ingest/batch", "HTTP :8000")
    Rel(api,      pg,       "SQL queries",     "asyncpg :5432")
    Rel(api,      redis,    "PUBLISH / SUBSCRIBE", "redis-py :6379")
    Rel(tracker,  redis,    "n/a (indirect via API)", "")
    Rel(migrator, pg,       "alembic upgrade head", "psycopg2 :5432")
```

---

## 3. Tracker Service — Internal Component Diagram

```mermaid
graph TD
    subgraph CCTV["Input Layer"]
        V1[CAM 1 · Entrance]
        V2[CAM 2 · Aisle]
        V3[CAM 3 · Skincare]
        V4[CAM 4 · Makeup]
        V5[CAM 5 · Checkout]
    end

    subgraph INGESTOR["ingestor.py — Frame Extraction"]
        FE["VideoIngestor\nevery 3rd frame\nOpenCV VideoCapture"]
    end

    subgraph DETECT["detector.py — Detection"]
        YOLO["YOLOv11n\nUltralytics\nCOCO class=0 (person)"]
        BT["ByteTrack\nStable track_id\nacross frames"]
        STAFF["Staff Heuristic\naspect ratio > 3.0\n→ person_class=staff"]
    end

    subgraph ZONE["zone_engine.py — Spatial Context"]
        ZE["ZoneEngine\nShapely Point-in-Polygon\nnormalised [0,1] coords"]
        ZONES["20 Store Zones\nEntrance · Exit\n8 Skincare · 8 Makeup\nAisle · Accessories"]
    end

    subgraph ENGINE["event_engine.py — Business Events"]
        FSM["TrackFSM per track_id\nNEW → ACTIVE → DWELL → EXITED"]
        EE["EventEngine\nZone transitions\nDwell threshold 20s\nGroup detection"]
    end

    subgraph ANOMALY["anomaly_rules.py — Anomaly Detection"]
        CS["CROWD_SURGE\nocc > 2× rolling mean\n5-min bucket"]
        LS["LONG_STAY\nstay > 30 min\nper-track timer"]
        ER["EXCESS_REENTRY\ntrack enters ≥ 3×\ncross-session"]
        CF["CAMERA_FAILURE\nno detections > 30s\nfeed freeze"]
    end

    subgraph CLIENT["api_client.py — Event Push"]
        AC["ApiClient\nbuffer 50 events\nflush every 1s\nat-least-once delivery"]
    end

    V1 & V2 & V3 & V4 & V5 -->|"MP4 / RTSP"| FE
    FE -->|"np.ndarray frame"| YOLO
    YOLO -->|"bboxes + class"| BT
    BT -->|"track_id + bbox"| STAFF
    STAFF -->|"detection dict"| ZE
    ZONES -.->|"polygon config"| ZE
    ZE -->|"zones_for_point()"| FSM
    FSM -->|"state transitions"| EE
    EE -->|"queue_event()"| AC
    EE -->|"occupancy stats"| CS
    FSM -->|"track age / reentry"| LS & ER
    FE -->|"frame presence"| CF
    CS & LS & ER & CF -->|"queue_event(ANOMALY)"| AC
    AC -->|"POST /api/v1/ingest/batch"| API["FastAPI :8000"]
```

---

## 4. FastAPI — Router & Service Layer

```mermaid
graph LR
    subgraph ROUTERS["Routers (app/routers/)"]
        R_H["/health\nGET"]
        R_M["/metrics\nGET · Prometheus"]
        R_WS["/ws/events\nWebSocket"]
        R_E["/api/v1/events\nGET"]
        R_A["/api/v1/anomalies\nGET · PATCH"]
        R_F["/api/v1/funnel\nGET"]
        R_SM["/api/v1/store-metrics/*\nGET × 3"]
        R_I["/api/v1/ingest/*\nPOST × 3"]
    end

    subgraph SERVICES["Services (app/services/)"]
        S_E["EventService\nlist_events()"]
        S_AN["AnomalyService\nlist_anomalies()\nresolve_anomaly()"]
        S_AN2["AnalyticsService\nget_funnel()"]
        S_M["MetricsService\nget_summary()\nget_peak_hours()\nget_zone_popularity()"]
    end

    subgraph REPOS["Repositories (app/repositories/)"]
        RP_E["EventRepository\ncursor pagination\nfunnel_counts()"]
        RP_A["AnomalyRepository\ncursor pagination\nresolve()"]
        RP_M["MetricsRepository\ntotal_visitors()\nconversion_rate()\nzone_visit_counts()\ntransaction_count()\ntotal_gmv()"]
    end

    subgraph DB["PostgreSQL Tables"]
        T_E[("events")]
        T_S[("sessions")]
        T_A[("anomalies")]
        T_Z[("zones")]
        T_C[("cameras")]
        T_L[("store_layouts")]
    end

    R_E --> S_E --> RP_E --> T_E
    R_A --> S_AN --> RP_A --> T_A
    R_F --> S_AN2 --> RP_E
    R_SM --> S_M --> RP_M --> T_E & T_S & T_A & T_Z
    R_I -->|"direct DB write\n+ Redis PUBLISH"| T_E
    R_WS -->|"Redis SUBSCRIBE\nstore:events"| REDIS[("Redis\nPubSub")]
    R_H -->|"SELECT 1"| T_E
```

---

## 5. Database Schema (ERD)

```mermaid
erDiagram
    cameras {
        uuid    id          PK
        string  name
        string  location
        string  rtsp_url
        int     resolution_w
        int     resolution_h
        int     fps
        string  status
        ts      created_at
    }

    store_layouts {
        uuid    id          PK
        int     version
        string  name
        jsonb   floor_plan
        bool    is_active
        ts      created_at
    }

    zones {
        uuid    id          PK
        uuid    layout_id   FK
        uuid    camera_id   FK
        string  name
        string  zone_type
        jsonb   polygon
        string  color
        jsonb   metadata
        ts      created_at
    }

    sessions {
        uuid    id          PK
        string  track_id
        uuid    camera_id   FK
        string  person_class
        ts      entered_at
        ts      exited_at
        uuid    entry_zone_id FK
        uuid    exit_zone_id  FK
        jsonb   metadata
    }

    events {
        uuid    id          PK
        string  event_type
        ts      timestamp
        uuid    camera_id   FK
        string  track_id
        uuid    session_id  FK
        uuid    zone_id     FK
        string  group_id
        string  person_class
        float   confidence
        jsonb   bbox
        jsonb   metadata
    }

    anomalies {
        uuid    id          PK
        uuid    event_id    FK
        string  anomaly_type
        string  severity
        bool    resolved
        ts      resolved_at
        string  resolved_by
        text    notes
        ts      detected_at
    }

    cameras       ||--o{ zones    : "covers"
    cameras       ||--o{ events   : "captures"
    cameras       ||--o{ sessions : "records"
    store_layouts ||--o{ zones    : "contains"
    sessions      ||--o{ events   : "groups"
    zones         ||--o{ events   : "location"
    events        ||--o| anomalies : "triggers"
```

---

## 6. Event Ingestion Sequence

```mermaid
sequenceDiagram
    participant CAM  as CCTV Camera
    participant TRK  as Tracker Service
    participant API  as FastAPI
    participant PG   as PostgreSQL
    participant RDS  as Redis Pubsub
    participant WS   as WebSocket Client
    participant DASH as Dashboard (Next.js)

    Note over TRK: Process every 3rd frame
    CAM->>TRK: MP4 frame (ndarray)
    TRK->>TRK: YOLOv11: detect persons
    TRK->>TRK: ByteTrack: assign track_ids
    TRK->>TRK: ZoneEngine: point-in-polygon
    TRK->>TRK: EventEngine: FSM transitions
    TRK->>TRK: AnomalyRules: crowd/dwell/reentry check

    Note over TRK,API: Batch flush every 1s (up to 50 events)
    TRK->>API: POST /api/v1/ingest/batch [{event_type, track_id, zone_id, ...}]
    API->>PG: INSERT INTO events (batch)
    API->>RDS: PUBLISH store:events {event_json}
    API-->>TRK: 201 {inserted: N, ids: [...]}

    Note over RDS,DASH: Real-time fan-out
    RDS-->>WS: message {event_json}
    WS-->>DASH: ws.onmessage → update live feed

    Note over DASH,API: KPI polling (10s interval)
    DASH->>API: GET /api/v1/store-metrics/summary
    API->>PG: COUNT(ENTRY), occupancy, avg dwell, peak_hour
    API-->>DASH: {total_visitors, occupancy, conversion_rate, ...}
    DASH->>DASH: Re-render KPI cards
```

---

## 7. Anomaly Detection Flow

```mermaid
flowchart TD
    START([Every frame processed]) --> CHECK_CROWD

    CHECK_CROWD{Occupancy >\n2× rolling mean?}
    CHECK_CROWD -->|Yes| FIRE_CROWD[Fire CROWD_SURGE\nHIGH severity]
    CHECK_CROWD -->|No| CHECK_DWELL

    CHECK_DWELL{Any track\nage > 30 min?}
    CHECK_DWELL -->|Yes| FIRE_DWELL[Fire LONG_STAY\nMEDIUM severity]
    CHECK_DWELL -->|No| CHECK_REENTRY

    CHECK_REENTRY{Any track\nentries ≥ 3?}
    CHECK_REENTRY -->|Yes| FIRE_REENTRY[Fire EXCESS_REENTRY\nMEDIUM severity]
    CHECK_REENTRY -->|No| CHECK_CAM

    CHECK_CAM{No detections\n> 30 seconds?}
    CHECK_CAM -->|Yes| FIRE_CAM[Fire CAMERA_FAILURE\nHIGH severity]
    CHECK_CAM -->|No| DEDUP

    FIRE_CROWD & FIRE_DWELL & FIRE_REENTRY & FIRE_CAM --> DEDUP

    DEDUP{Key already\nfired this\nwindow?}
    DEDUP -->|Yes| SKIP[Skip — dedup cache hit]
    DEDUP -->|No| QUEUE[queue_event ANOMALY\nto ApiClient buffer]

    QUEUE --> INGEST[POST /api/v1/ingest/batch\nmetadata.anomaly_type]
    INGEST --> PGSTORE[(PostgreSQL\nanomalies table)]
    INGEST --> RESOLVE

    RESOLVE{Manager\nresolves?}
    RESOLVE -->|PATCH /anomalies/id/resolve| CLOSED[resolved=true\nresolved_at=now()]
```

---

## 8. Infrastructure & Deployment

```mermaid
graph TB
    subgraph HOST["Host Machine (Linux / Windows WSL2)"]

        subgraph COMPOSE["docker compose up"]
            direction TB

            subgraph INFRA["Infrastructure (starts first)"]
                PG["postgres:16-alpine\n:5432\nHealthcheck: pg_isready\nVolume: postgres_data"]
                RD["redis:7-alpine\n:6379\nappendonly yes\n256MB maxmemory\nVolume: redis_data"]
            end

            subgraph MIGRATE["Migrations (one-shot)"]
                MIG["migrator\nalembic upgrade head\nDepends: postgres healthy\nrestart: no"]
            end

            subgraph SERVICES["Application Services"]
                API["api (FastAPI)\n:8000\n4 uvicorn workers\nDepends: migrator OK\nHealthcheck: GET /health"]
                TRK["tracker (Python)\nDepends: api healthy\nVolume: /videos (CCTV MP4s)\nrestart: no"]
                FE["frontend (Next.js)\n:3000\nstandalone output\nDepends: api healthy"]
            end

            subgraph TOOLS["Dev Tools (--profile tools)"]
                PGA["pgadmin4:8\n:5050"]
                RCM["redis-commander\n:8081"]
            end
        end

        subgraph MAKEFILE["Makefile Commands"]
            MK1["make up        → docker compose up --build -d"]
            MK2["make seed-demo → synthetic footfall + anomalies"]
            MK3["make seed-csv  → POS CSV → ENTRY/EXIT events"]
            MK4["make seed-layout → cameras + zones"]
            MK5["make test      → pytest 26 tests"]
            MK6["make demo      → up + seed-layout + seed-demo"]
        end
    end

    PG --- MIG
    MIG --- API
    RD --- API
    API --- TRK
    API --- FE

    style HOST fill:#0f172a,color:#e2e8f0,stroke:#334155
    style COMPOSE fill:#1e293b,color:#e2e8f0,stroke:#475569
    style INFRA fill:#0f2040,color:#e2e8f0,stroke:#3b82f6
    style MIGRATE fill:#1a1a0f,color:#fbbf24,stroke:#f59e0b
    style SERVICES fill:#0f2020,color:#e2e8f0,stroke:#22c55e
    style TOOLS fill:#1a0f1a,color:#a78bfa,stroke:#8b5cf6
```

---

## 9. Data Flow — CCTV to Dashboard KPI

```mermaid
flowchart LR
    subgraph INPUT["Raw Inputs"]
        V["5× CCTV\nMP4 / RTSP"]
        C["POS CSV\n101 transactions"]
        L["Store Layout\nExcel (20 zones)"]
    end

    subgraph PROCESS["Processing"]
        DET["YOLOv11n\nDetect persons\nbbox + confidence"]
        TRK["ByteTrack\nStable track_id\nacross frames"]
        ZON["ZoneEngine\nShapely polygons\npoint-in-polygon"]
        EVT["EventEngine\nFSM transitions\nbusiness events"]
    end

    subgraph STORE["Storage"]
        EV[("events\n· ENTRY\n· EXIT\n· ZONE_ENTER\n· DWELL_STARTED\n· GROUP_ENTRY\n· ANOMALY")]
        SE[("sessions\n· entered_at\n· exited_at\n· person_class")]
        AN[("anomalies\n· type\n· severity\n· resolved")]
        ZN[("zones\n· name\n· polygon\n· zone_type")]
    end

    subgraph ANALYTICS["Analytics Queries"]
        Q1["total_visitors = COUNT DISTINCT track_id\nWHERE event_type = ENTRY"]
        Q2["occupancy = entered - exited\n(all time)"]
        Q3["avg_dwell = AVG(exited_at - entered_at)\nFROM sessions"]
        Q4["peak_hour = MAX COUNT(ENTRY)\nGROUP BY date_part hour"]
        Q5["conversion = COUNT DISTINCT order_id\n÷ total_visitors × 100"]
        Q6["zone_popularity = COUNT ZONE_ENTER\nJOIN zones ON zone_id\nORDER BY count DESC"]
    end

    subgraph OUTPUT["Dashboard KPIs"]
        K1["120 Visitors Today"]
        K2["15 In Store Now"]
        K3["8m 0s Avg Dwell"]
        K4["17:00 Peak Hour"]
        K5["42.5% Conversion"]
        K6["Makeup Row #1 Zone"]
    end

    V --> DET --> TRK --> ZON --> EVT --> EV & SE
    C -->|"seed_from_csv.py"| EV & SE
    L -->|"parse_layout.py"| ZN
    EVT --> AN

    EV --> Q1 & Q2 & Q4 & Q5 & Q6
    SE --> Q3
    ZN --> Q6

    Q1 --> K1
    Q2 --> K2
    Q3 --> K3
    Q4 --> K4
    Q5 --> K5
    Q6 --> K6
```

---

## 10. Frontend Architecture

```mermaid
graph TB
    subgraph NEXTJS["Next.js 14 App Router"]
        direction TB

        subgraph LAYOUT["app/layout.tsx"]
            HTML["HTML dark class\n+ Sidebar\n+ main wrapper"]
        end

        subgraph PAGES["Pages (Server Components)"]
            P1["app/dashboard/page.tsx"]
            P2["app/events/page.tsx"]
            P3["app/anomalies/page.tsx"]
            P4["app/funnel/page.tsx"]
        end

        subgraph CONTENT["Content (Client Components — 'use client')"]
            C1["DashboardContent\n8 KPI cards\nHourly BarChart\nWS live feed"]
            C2["EventsContent\nFilterable table\n5s auto-refresh"]
            C3["AnomaliesContent\nSeverity summary\nResolve button"]
            C4["FunnelContent\nHorizontal BarChart\nDrop-off analysis"]
        end

        subgraph HOOKS["hooks/"]
            H1["useApi(fetcher, intervalMs)\nloading / error / data / refetch"]
            H2["useWebSocketEvents(max)\nWebSocket + Redis pubsub\nDB poll fallback"]
            H3["useAutoRefresh(cb, ms)\nsetInterval wrapper"]
        end

        subgraph LIB["lib/"]
            L1["api.ts\nTyped fetch wrappers\nall endpoints"]
            L2["utils.ts\ncn(), formatDuration()\nformatHour(), formatTs()"]
        end

        subgraph UI["components/ui/  (shadcn-style)"]
            U1["Card / CardHeader\nCardContent / CardTitle"]
            U2["Badge (7 variants)\ndestructive/success/info/warning/purple"]
            U3["Button (CVA variants)"]
            U4["Skeleton (shimmer)"]
            U5["Table / TableRow\nTableHead / TableCell"]
            U6["Select"]
        end

        subgraph CHARTS["Recharts"]
            CH1["BarChart + Cell\nPeak hours footfall"]
            CH2["BarChart horizontal\nFunnel stages"]
        end
    end

    LAYOUT --> PAGES
    P1 --> C1
    P2 --> C2
    P3 --> C3
    P4 --> C4

    C1 --> H1 & H2
    C2 --> H1
    C3 --> H1
    C4 --> H1
    H1 --> L1
    H2 -->|"ws://host/ws/events"| WS[("WebSocket\nRedis Pubsub")]

    C1 & C2 & C3 & C4 --> UI
    C1 --> CHARTS
    C4 --> CHARTS
```

---

## 11. Security & Observability

```mermaid
mindmap
  root((Store Intelligence))
    Observability
      Prometheus
        http_requests_total counter
        http_request_duration_seconds histogram
        store_active_tracks gauge
        store_open_anomalies gauge
        store_events_ingested_total counter
      Structured Logging
        structlog JSON format
        request_id on every log line
        event_type + track_id context
      Health Checks
        GET /health → postgres SELECT 1
        Docker healthcheck all containers
        pgAdmin + Redis Commander optional
    Security
      CORS
        allow_origins wildcard
        configurable via env
      Input Validation
        Pydantic v2 schemas
        event_type StrEnum validation
        confidence ge=0 le=1
        limit ge=1 le=500
      Error Handling
        RequestIDMiddleware
        http_exception_handler
        validation_exception_handler
        unhandled_exception_handler
    Reliability
      Cursor Pagination
        base64 encoded timestamp+id
        no OFFSET degradation
      Redis Fallback
        WS → DB poll if Redis down
        API client re-queues on flush fail
      Connection Pooling
        asyncpg pool_size=10
        max_overflow=20
        pool_pre_ping=True
```

---

## Summary Table

| Layer | Technology | Purpose |
|---|---|---|
| Detection | YOLOv11n (Ultralytics) | Person bounding boxes, COCO class 0 |
| Tracking | ByteTrack (via Ultralytics) | Stable track_id across frames |
| Zone Mapping | Shapely | Point-in-polygon, normalised coords |
| Event Engine | Python FSM | Tracks → ENTRY/EXIT/ZONE/DWELL events |
| Anomaly Engine | Rule-based Python | CROWD_SURGE/LONG_STAY/REENTRY/CAM_FAIL |
| API | FastAPI + asyncpg | 10+ REST + WebSocket endpoints |
| Database | PostgreSQL 16 | Event store, 6 tables, Alembic migrations |
| Cache / Pubsub | Redis 7 | WebSocket fan-out via `store:events` channel |
| Frontend | Next.js 14 + shadcn/ui | 4 pages, WS live feed, 5–10s polling |
| Infra | Docker Compose | 6-container orchestration, one command startup |
| Observability | Prometheus + structlog | Metrics scrape + JSON logs |
| Tests | pytest + pytest-asyncio | 26 tests, mocked deps, no DB required |
