"""
Event Engine — converts ByteTrack detections into business events.

Per-track FSM:
  NEW → ACTIVE (on first detection)
  ACTIVE → DWELL (stationary > dwell_threshold_s)
  ACTIVE / DWELL → EXITED (track disappears in exit zone)

Emits: ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, DWELL_STARTED, DWELL_ENDED,
       GROUP_ENTRY, STAFF_DETECTED
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import auto, Enum
from typing import TYPE_CHECKING

import structlog

from tracker.zone_engine import Zone, ZoneEngine

if TYPE_CHECKING:
    from tracker.api_client import ApiClient

logger = structlog.get_logger(__name__)


class TrackState(Enum):
    NEW = auto()
    ACTIVE = auto()
    DWELL = auto()
    EXITED = auto()


@dataclass
class TrackRecord:
    track_id: str
    state: TrackState = TrackState.NEW
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    person_class: str = "customer"
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_position: tuple[float, float] = (0.0, 0.0)
    current_zones: set[str] = field(default_factory=set)
    dwell_start: datetime | None = None
    entry_emitted: bool = False
    reentry_count: int = 0


class EventEngine:
    def __init__(
        self,
        api: "ApiClient",
        zone_engine: ZoneEngine,
        camera_id: str,
        dwell_threshold_s: float = 20.0,
    ) -> None:
        self.api = api
        self.zones = zone_engine
        self.camera_id = camera_id
        self.dwell_threshold_s = dwell_threshold_s
        self._tracks: dict[str, TrackRecord] = {}
        # occupancy rolling window for crowd-surge detection
        self._occupancy_history: list[int] = []

    # ------------------------------------------------------------------
    # Main update — called per frame for each active detection
    # ------------------------------------------------------------------
    def update(
        self,
        detections: list[dict],   # [{track_id, bbox, confidence, person_class}]
        frame_w: int,
        frame_h: int,
        timestamp: datetime,
    ) -> None:
        active_ids: set[str] = set()

        for det in detections:
            tid = str(det["track_id"])
            active_ids.add(tid)
            bbox = det["bbox"]           # {x, y, w, h} pixels
            conf = float(det.get("confidence", 0.9))
            pclass = det.get("person_class", "customer")

            nx, ny = ZoneEngine.bbox_centre(bbox, frame_w, frame_h)
            current_zones = self.zones.zones_for_point(nx, ny)
            zone_ids = {z.id for z in current_zones}

            if tid not in self._tracks:
                self._tracks[tid] = TrackRecord(
                    track_id=tid,
                    person_class=pclass,
                    first_seen=timestamp,
                    last_seen=timestamp,
                    last_position=(nx, ny),
                    current_zones=zone_ids,
                )
                self._on_new_track(tid, current_zones, bbox, conf, timestamp)
            else:
                self._on_update_track(tid, current_zones, zone_ids, bbox, conf, timestamp, nx, ny)

        # Handle disappeared tracks
        disappeared = set(self._tracks) - active_ids
        for tid in disappeared:
            self._on_track_lost(tid, timestamp)

        # Dwell check for active tracks
        self._check_dwell(timestamp)

        # Occupancy tracking
        occupancy = len([t for t in self._tracks.values() if t.state != TrackState.EXITED])
        self._occupancy_history.append(occupancy)
        if len(self._occupancy_history) > 300:
            self._occupancy_history.pop(0)

    # ------------------------------------------------------------------
    def _on_new_track(
        self,
        tid: str,
        zones: list[Zone],
        bbox: dict,
        conf: float,
        timestamp: datetime,
    ) -> None:
        rec = self._tracks[tid]
        rec.state = TrackState.ACTIVE

        in_entrance = any(z.zone_type == "ENTRANCE" for z in zones)
        if in_entrance or not zones:
            if not rec.entry_emitted:
                rec.entry_emitted = True
                self.api.queue_event(
                    event_type="ENTRY",
                    timestamp=timestamp,
                    camera_id=self.camera_id,
                    track_id=tid,
                    session_id=rec.session_id,
                    person_class=rec.person_class,
                    confidence=conf,
                    bbox=bbox,
                )
                if rec.person_class == "staff":
                    self.api.queue_event(
                        event_type="STAFF_DETECTED",
                        timestamp=timestamp,
                        camera_id=self.camera_id,
                        track_id=tid,
                        session_id=rec.session_id,
                        person_class="staff",
                        confidence=conf,
                    )
                logger.debug("entry", tid=tid, pclass=rec.person_class)

        for z in zones:
            self.api.queue_event(
                event_type="ZONE_ENTER",
                timestamp=timestamp,
                camera_id=self.camera_id,
                track_id=tid,
                session_id=rec.session_id,
                zone_id=z.id,
                person_class=rec.person_class,
                confidence=conf,
            )

    def _on_update_track(
        self,
        tid: str,
        current_zones: list[Zone],
        zone_ids: set[str],
        bbox: dict,
        conf: float,
        timestamp: datetime,
        nx: float,
        ny: float,
    ) -> None:
        rec = self._tracks[tid]
        rec.last_seen = timestamp
        prev_zone_ids = rec.current_zones

        # Zone transitions
        entered = zone_ids - prev_zone_ids
        exited = prev_zone_ids - zone_ids

        for z in current_zones:
            if z.id in entered:
                self.api.queue_event(
                    event_type="ZONE_ENTER",
                    timestamp=timestamp,
                    camera_id=self.camera_id,
                    track_id=tid,
                    session_id=rec.session_id,
                    zone_id=z.id,
                    person_class=rec.person_class,
                    confidence=conf,
                )
        for zid in exited:
            self.api.queue_event(
                event_type="ZONE_EXIT",
                timestamp=timestamp,
                camera_id=self.camera_id,
                track_id=tid,
                session_id=rec.session_id,
                zone_id=zid,
                person_class=rec.person_class,
                confidence=conf,
            )

        rec.current_zones = zone_ids
        rec.last_position = (nx, ny)

        # Movement → reset dwell if moved significantly
        if rec.state == TrackState.DWELL:
            px, py = rec.last_position
            dist = ((nx - px) ** 2 + (ny - py) ** 2) ** 0.5
            if dist > 0.05:
                rec.state = TrackState.ACTIVE
                rec.dwell_start = None
                self.api.queue_event(
                    event_type="DWELL_ENDED",
                    timestamp=timestamp,
                    camera_id=self.camera_id,
                    track_id=tid,
                    session_id=rec.session_id,
                    person_class=rec.person_class,
                    confidence=conf,
                )

    def _on_track_lost(self, tid: str, timestamp: datetime) -> None:
        rec = self._tracks[tid]
        if rec.state == TrackState.EXITED:
            return
        rec.state = TrackState.EXITED

        in_exit = self.zones.is_exit(rec.last_position[0], rec.last_position[1])
        self.api.queue_event(
            event_type="EXIT",
            timestamp=timestamp,
            camera_id=self.camera_id,
            track_id=tid,
            session_id=rec.session_id,
            person_class=rec.person_class,
            confidence=0.85,
            metadata={"via_exit_zone": in_exit},
        )
        logger.debug("exit", tid=tid, in_exit_zone=in_exit)

    def _check_dwell(self, timestamp: datetime) -> None:
        for rec in self._tracks.values():
            if rec.state != TrackState.ACTIVE:
                continue
            age_s = (timestamp - rec.last_seen).total_seconds()
            if age_s > self.dwell_threshold_s:
                rec.state = TrackState.DWELL
                rec.dwell_start = timestamp
                self.api.queue_event(
                    event_type="DWELL_STARTED",
                    timestamp=timestamp,
                    camera_id=self.camera_id,
                    track_id=rec.track_id,
                    session_id=rec.session_id,
                    person_class=rec.person_class,
                    confidence=0.9,
                )

    def emit_group_entry(self, track_ids: list[str], group_id: str, timestamp: datetime) -> None:
        for tid in track_ids:
            rec = self._tracks.get(tid)
            if rec:
                self.api.queue_event(
                    event_type="GROUP_ENTRY",
                    timestamp=timestamp,
                    camera_id=self.camera_id,
                    track_id=tid,
                    session_id=rec.session_id,
                    group_id=group_id,
                    person_class=rec.person_class,
                    confidence=0.8,
                )

    @property
    def active_occupancy(self) -> int:
        return len([t for t in self._tracks.values() if t.state != TrackState.EXITED])

    @property
    def mean_occupancy(self) -> float:
        if not self._occupancy_history:
            return 0.0
        return sum(self._occupancy_history) / len(self._occupancy_history)
