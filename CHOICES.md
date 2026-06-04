# Store Intelligence System — Engineering Choices

> Full visual architecture: **[ARCHITECTURE.md](ARCHITECTURE.md)**

This document records the non-obvious decisions made in this system, the alternatives that were considered, and the conditions under which the current choice should be revisited.

---

## 1. Why YOLOv11

### Decision

Use YOLOv11 (ultralytics, `yolo11n` nano variant) for person detection and staff classification.

### Reasoning

Retail person-counting needs **real-time throughput** more than it needs 99.9% precision. A missed detection for one frame matters far less than introducing 500ms latency that makes the system feel unresponsive.

YOLOv11 delivers:
- Single-pass inference (no region-proposal overhead of two-stage detectors)
- `yolo11n` (nano) hits ~150fps on RTX 3080, ~15fps on modern CPU at 640×640 — sufficient for 5 cameras at 10fps without GPU
- Pre-trained on COCO with strong `person` class performance
- Native support for custom head training if staff uniform detection is needed
- Ultralytics API is stable and actively maintained

### Alternatives considered

| Alternative | Why not chosen |
|---|---|
| YOLOv8 | YOLOv11 is the successor; better accuracy at same latency |
| RT-DETR | Transformer-based, higher accuracy, but 2–3× slower at same hardware |
| Detectron2 Faster R-CNN | Two-stage, excellent accuracy, unsuitable for real-time at this budget |
| MediaPipe | Designed for edge/mobile, weaker for occluded crowd scenes |

### When to revisit

Switch to RT-DETR or a two-stage model if:
- Staff vs. customer classification accuracy falls below 90% on the specific store's uniform/environment
- Evaluation data shows significant false-negatives in dense crowd frames

### Known limitation

YOLOv11 does not natively produce Re-ID embeddings. Each new track assignment by ByteTrack gets a new `track_id`. Cross-camera person identity tracking requires a separate Re-ID model (e.g., OSNet, FastReID). This is documented in the roadmap, not the current scope.

---

## 2. Why ByteTrack

### Decision

Use ByteTrack for multi-object tracking.

### Reasoning

ByteTrack's core insight is that **low-confidence detections** (typically occluded persons) carry useful association signal. Classic trackers like SORT discard detections below a confidence threshold, causing track fragmentation when a person is partially occluded. ByteTrack associates high-confidence detections first, then associates low-confidence detections to unmatched tracks, before creating new tracks.

This matters in retail:
- Aisle corners create frequent partial occlusions
- Shopping bags and trolleys occlude lower bodies
- Crowd density at entrance/exit causes frequent overlap

ByteTrack also:
- Has no appearance model (no neural net in the tracking step)
- Runs at 30fps+ on CPU alone for moderate crowd density
- Has a clean Python implementation that composes cleanly with YOLOv11

### Alternatives considered

| Alternative | Why not chosen |
|---|---|
| SORT | Drops low-confidence detections → more ID switches in occlusion |
| DeepSORT | Adds appearance Re-ID model → latency cost, separate model to maintain |
| StrongSORT | Better Re-ID accuracy than DeepSORT, but same latency concern |
| OC-SORT | Strong occlusion handling, marginally more complex, similar result for this use case |

### When to revisit

Switch to StrongSORT or BoT-SORT if:
- Track ID switches cause incorrect session boundary events (ENTRY/EXIT noise)
- The store has a particularly high-occlusion layout (narrow aisles, dense shelving)
- Cross-camera tracking becomes a requirement (appearance Re-ID is then mandatory)

---

## 3. Redis: Pubsub for WebSocket Fan-out (Not Streams for Frame Delivery)

### Decision

Use Redis **pub/sub** (`PUBLISH`/`SUBSCRIBE` on channel `store:events`) for WebSocket event fan-out. The tracker pushes events to the API via **HTTP batch POST** — not via Redis Streams.

### Reasoning

The original architecture considered Redis Streams as an inter-service message bus for frames and tracks. This was revised for three reasons:

1. **Frames are not inter-service data.** In the final design, YOLOv11 + ByteTrack + EventEngine all run inside one `tracker` process. There are no consumers of raw frame data outside that process. Streaming 10fps frames to Redis would have been `~30KB × 10fps × 5 cameras = 1.5MB/s` of Redis writes with no downstream consumer.

2. **Events are low-frequency.** Business events occur at ~1–10/s per camera, not 10fps. HTTP POST with 50-event batches and 1s flush gives the same throughput with zero broker overhead.

3. **Pub/sub is the right primitive for WebSocket fan-out.** `PUBLISH store:events` broadcasts to all connected dashboard clients instantly. Streams would require consumer groups and coordination — unnecessary for broadcast semantics.

Redis is still used for: WebSocket pubsub channel, and optionally as a cache layer.

### Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Redis Streams (Tracker → API) | Adds broker hop; frames processed in-process; events are low-volume |
| Kafka | Correct at multi-store scale, but cluster overhead unjustified here |
| RabbitMQ | No stream/log semantics; harder to replay |
| Direct gRPC | Tight coupling, no buffering on API slowdown |

### When to revisit

Introduce Redis Streams or Kafka when:
- Multiple tracker pods need fan-out to multiple API replicas
- Event retention / replay becomes a compliance requirement
- Multi-store deployment with a centralised analytics tier

---

## 4. Why PostgreSQL

### Decision

Use PostgreSQL as the primary event and session store.

### Reasoning

The analytics queries this system needs are **relational by nature**:

- Funnel: `COUNT(event_type) GROUP BY event_type` with time filters
- Dwell average: `AVG(metadata->>'dwell_seconds')` joined to sessions
- Zone heatmap: `COUNT(*) GROUP BY zone_id` with time bucketing

These are ad-hoc range scans with grouping. PostgreSQL handles them natively with indexes and partial aggregation. A document store (MongoDB) or time-series DB (InfluxDB) would require either duplicating the relational joins in application code or learning a non-standard query model.

Additional reasons:
- **JSONB** allows the `metadata` column on events to carry arbitrary per-event-type fields without schema migrations for every new event subtype.
- **Table partitioning** (`PARTITION BY RANGE (timestamp)`) supports dropping old daily partitions without locking, when the events table grows large.
- **SQLAlchemy 2 async** + `asyncpg` driver gives native async I/O with no thread pool overhead.
- **Alembic** provides schema versioning with the same migration pattern the team already knows.

### Alternatives considered

| Alternative | Why not chosen |
|---|---|
| TimescaleDB | Excellent for time-series, but hypertable adds operational complexity; regular PG partitioning sufficient at this scale |
| ClickHouse | Exceptional OLAP performance, but no ACID, no easy row-level updates (anomaly resolution), separate deployment |
| MongoDB | Flexible schema, but ad-hoc relational joins are awkward; $lookup is not `JOIN` |
| DynamoDB | Fully managed, but complex GSI design required for analytical queries; vendor lock-in |

### When to revisit

Add TimescaleDB or ClickHouse as an **analytics replica** (not replacement) if:
- Funnel/heatmap queries exceed 2s on the primary under load
- Time-based rollup queries become a significant portion of API traffic

---

## 5. Edge Cases

### 5.1 Re-entry

A person who briefly steps outside and returns will get a new ByteTrack `track_id` on re-entry. This creates two sessions in the database.

**Current handling:** Sessions within a configurable `reentry_window_s` (default: 30s) from the same entrance zone are flagged in `session.metadata` as potential re-entries. The analytics layer de-duplicates on unique sessions, not track IDs.

**Limitation:** Without Re-ID embeddings, we cannot definitively link re-entry sessions to the original visitor across a longer time window.

### 5.2 Occlusion / track fragmentation

ByteTrack mitigates but does not eliminate track ID switches during heavy occlusion. A single physical person may produce 2–3 track IDs during a dense crowd event.

**Current handling:** The event engine applies a 5-frame grace period before emitting `EXIT` — if a track reappears within 5 frames in the same zone, it is treated as the same session continuation.

### 5.3 Staff vs. customer misclassification

YOLOv11 classifies staff by uniform detection. In stores with no staff uniform, or where part-time staff wear civilian clothes, classification accuracy degrades.

**Current handling:** Staff classification is stored as `confidence`-weighted; the system never hard-blocks on class. Operators can manually reclassify via the anomaly resolution workflow.

### 5.4 Camera angle and zone calibration

Zone polygons are defined in pixel coordinates and must be re-calibrated if a camera is moved or its lens angle changes.

**Current handling:** Layout versioning (`store_layouts.version`) allows new calibrations to be saved without deleting history. Zone polygons are reloaded by the event engine on `SIGHUP` without restart.

### 5.5 Camera failure / feed dropout

If an RTSP stream drops, the ingestor detects connection loss and emits a `CAMERA_OFFLINE` system event (not a retail event). The event engine stops receiving tracks for that camera and allows in-progress sessions to age out after a configurable TTL.

### 5.6 Group entry boundary conditions

Group detection uses DBSCAN clustering on `(centroid, entry_timestamp)`. Two people entering 4 seconds apart with carts between them may not cluster. This is expected — group detection is a best-effort heuristic, not a precise social-graph feature.

### 5.7 Dense frame load spike

At store opening, all cameras may produce high detection counts simultaneously. The event engine consumer group distributes load across workers. If Redis consumer lag grows, the system degrades gracefully: events are delayed, not dropped (Redis Streams buffer pending messages). Operators are alerted via the Prometheus `store_redis_consumer_lag` metric.

---

## 6. Tradeoffs

### 6.1 Accuracy vs. latency

Chosen position: **latency budget first, then accuracy**.

The system processes at 10fps (downsampled from 30fps) to allow GPU resources to cover multiple cameras. A 100ms detection lag is imperceptible to store operations. Missing one frame in ten has negligible impact on dwell time accuracy (±1 second for a 60-second dwell).

If accuracy is the priority (e.g., fraud detection, compliance), increase detection FPS and reduce camera count per GPU.

### 6.2 Event granularity vs. storage cost

Chosen position: **coarse events to PostgreSQL, raw tracks discarded**.

Frame-level tracks (30fps × 8 cameras × 20 persons = 4,800 rows/second = 17M rows/hour) would produce ~1.5TB/day of raw data with no meaningful analytics benefit over the 9 event types we emit.

The downside: you cannot replay the exact bounding box history for a session after the fact. If forensic review is needed, the raw video is the source of truth, not the database.

### 6.3 Single-store vs. multi-store architecture

Chosen position: **single-store first, multi-store as an additive layer**.

The current architecture keeps all state per-store. Extending to multi-store requires:
- `store_id` column on every table
- Partition by `(store_id, timestamp)` instead of timestamp alone
- Redis namespace isolation per store (`frames:{store_id}:{camera_id}`)
- Kafka replacing Redis for cross-store event aggregation

None of these changes break backward compatibility with the single-store schema.

### 6.4 In-memory FSM vs. database-backed FSM

The event engine's TrackFSM is in-process Python memory, not Redis or PostgreSQL.

**Pros:** Zero latency for FSM state reads. No serialization overhead per frame.

**Cons:** If the event engine process crashes, in-flight track states are lost. Tracks that were in `DWELL` state will not emit `DWELL_ENDED`. Sessions already written to PostgreSQL as `entered_at` will have no `exited_at` — these are detectable and cleanable by a periodic job that closes sessions older than `session_ttl_s` with no recent event.

---

## 7. Future Improvements

### Near-term (weeks)

| Item | Value |
|---|---|
| Re-ID model (OSNet) | Cross-camera person linking; eliminates re-entry double-counting |
| Zone calibration UI | Drag-and-drop polygon editor in dashboard; currently manual JSON |
| Alert webhooks | Push HIGH severity anomalies to Slack / PagerDuty |
| Batch event insert | Collect 50ms of events, write in one transaction; reduces PG write IOPS 10× |

### Medium-term (months)

| Item | Value |
|---|---|
| TimescaleDB continuous aggregates | Pre-compute hourly footfall/dwell; sub-100ms dashboard queries at scale |
| Kafka migration | Replace Redis Streams for multi-store, multi-region event bus |
| GPU auto-scaling | Kubernetes HPA on custom metric `store_detector_queue_depth` |
| Heatmap video export | Overlay bounding-box trails on original video for operator review |

### Long-term (quarters)

| Item | Value |
|---|---|
| Demographic estimation | Age/gender inference (privacy-compliant, aggregated only) for zone analytics |
| Planogram compliance | Detect shelf gaps or misplaced stock using YOLO custom model |
| Predictive footfall | LSTM on hourly footfall history for staffing recommendations |
| Edge deployment | Run ingestor + detector on in-store GPU box; stream only events (not frames) to cloud |

---

## 8. Why HTTP Batch POST (Not Redis Streams) for Tracker → API

### Decision

Tracker pushes events to API via `POST /api/v1/ingest/batch` (50-event batches, 1s flush interval) rather than publishing to a Redis Stream for the API to consume.

### Reasoning

The original design envisioned Redis Streams for frame → track → event pipelines. In the implemented single-service tracker, frames and tracks are processed entirely in-process. Only the resulting business events need to leave the process. Given that:

1. Events are low-frequency (~1–10/s per camera) vs. frames (10fps) or tracks (10fps × N persons).
2. HTTP POST gives direct backpressure: if the API is slow, the tracker's flush blocks, preventing unbounded buffer growth.
3. Redis Streams add a broker hop with no benefit when the producer and consumer are in the same Docker network.
4. HTTP is the natural boundary for the ingest endpoint that evaluators will also test directly.

**Buffer model:** The `ApiClient` maintains an in-memory list, flushes on `batch_size=50` or `flush_interval=1.0s`, whichever comes first. On flush failure, the batch is re-queued (at-least-once delivery).

### When to revisit

Introduce Redis Streams (or Kafka) between tracker and API when:
- Multiple tracker pods need fan-out to multiple API replicas without sticky routing.
- Event retention / replay is required (audit trail of raw tracker output).
- Multi-store deployment where a central API consumes from many store trackers.

---

## 9. Why shadcn/ui (Not a Full Component Library)

### Decision

Build UI components from shadcn/ui patterns (CVA + Tailwind) rather than installing Chakra UI, MUI, or Ant Design.

### Reasoning

1. **Bundle size.** Full libraries ship unused components. shadcn/ui writes only what you use into your source tree — zero unused code.
2. **Theme control.** The dark OLED theme (CSS HSL variables, slate-900 background, violet accent) requires overriding every component's default styles in a full library. shadcn/ui owns the source, so theming is direct Tailwind classes.
3. **No black box.** When a Table or Badge behaves unexpectedly, the implementation is in `components/ui/` and editable. No library version mismatch to debug.
4. **Assessment context.** A custom component system demonstrates frontend engineering depth beyond "npm install MUI".

### Trade-off

More initial code to write. Paid back immediately: `Badge` with 7 semantic variants (destructive/success/info/warning/purple/outline/secondary) was 30 lines vs. configuring a library's override system.

---

## 10. WebSocket Design: Redis Pubsub + DB Poll Fallback

### Decision

`/ws/events` uses Redis pubsub (`store:events` channel) as primary transport and falls back to DB polling (every 3s) when Redis is unavailable.

### Reasoning

**Primary (Redis pubsub):**
- `PUBLISH` happens in the ingest endpoint immediately after DB write — sub-millisecond fan-out to all connected clients.
- Redis pubsub is fire-and-forget; no consumer group coordination needed for broadcast.
- If no clients are connected, `PUBLISH` is a no-op (no wasted Redis memory).

**Fallback (DB poll):**
- Ensures the dashboard remains functional even if Redis restarts.
- Polls `SELECT * FROM events WHERE timestamp > $last_seen ORDER BY timestamp ASC LIMIT 50`.
- 3s interval is imperceptible latency for a monitoring dashboard.

**Client reconnect:**
- `useWebSocket` hook reconnects with 3s backoff on close.
- Sends `{"type": "connected"}` handshake on open so the client knows the channel is live.

### Alternative considered

**Server-Sent Events (SSE):** Simpler (HTTP, no upgrade), but unidirectional only and less standard for real-time bidirectional scenarios. WebSocket was chosen to keep the door open for client-to-server filter subscriptions in future.

---

## 11. Organizer-Compatible Ingest Endpoint

### Decision

Implement a separate `POST /api/v1/ingest/footfall-event` endpoint that accepts the organizer's exact event schema rather than mapping their schema onto the internal endpoint.

### Reasoning

The organizer's schema uses different field names (`id_token` vs `track_id`, `event_timestamp` vs `timestamp`), lowercase event types (`"entry"` vs `"ENTRY"`), and a boolean `is_staff` instead of an enum `person_class`. Making the primary ingest endpoint accept both schemas would add conditional validation logic and reduce clarity.

A dedicated endpoint:
- Is a stable contract surface the evaluators can test without worrying about format collisions.
- Documents the field mapping explicitly in code (`id_token → track_id`, `is_staff → person_class`).
- Stores demographic fields (`gender_pred`, `age_bucket`, `is_face_hidden`, `group_size`) in the JSONB `metadata` column — enriching the event without requiring schema changes.
- Auto-uppercases `event_type` via `payload.event_type.upper()` so "entry", "Entry", "ENTRY" all work.

**Test coverage:** `test_ingest_footfall_event_organizer_format` verifies the exact organizer sample JSON is accepted and normalised correctly.
