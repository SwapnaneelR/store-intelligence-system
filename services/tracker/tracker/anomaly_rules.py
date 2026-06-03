"""
Anomaly detection rules engine.
Runs post-frame checks against EventEngine state and fires anomaly events.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from tracker.api_client import ApiClient
    from tracker.event_engine import EventEngine, TrackRecord

logger = structlog.get_logger(__name__)


class AnomalyRulesEngine:
    def __init__(
        self,
        api: "ApiClient",
        camera_id: str,
        crowd_surge_ratio: float = 2.0,
        long_stay_threshold_s: float = 1800.0,
        excess_reentry_count: int = 3,
        camera_freeze_threshold_s: float = 30.0,
    ) -> None:
        self.api = api
        self.camera_id = camera_id
        self.crowd_surge_ratio = crowd_surge_ratio
        self.long_stay_threshold_s = long_stay_threshold_s
        self.excess_reentry_count = excess_reentry_count
        self.camera_freeze_threshold_s = camera_freeze_threshold_s

        self._fired_anomalies: set[str] = set()   # dedup key → avoid repeats
        self._last_detection_ts: datetime = datetime.now(timezone.utc)

    def run(self, engine: "EventEngine", timestamp: datetime) -> None:
        self._check_crowd_surge(engine, timestamp)
        self._check_long_stay(engine, timestamp)
        self._check_excess_reentry(engine, timestamp)

    def on_frame_with_detections(self, timestamp: datetime) -> None:
        self._last_detection_ts = timestamp

    def check_camera_freeze(self, timestamp: datetime) -> None:
        gap = (timestamp - self._last_detection_ts).total_seconds()
        key = f"camera_freeze_{self.camera_id}_{int(timestamp.timestamp() // 60)}"
        if gap > self.camera_freeze_threshold_s and key not in self._fired_anomalies:
            self._fired_anomalies.add(key)
            self.api.queue_event(
                event_type="ANOMALY",
                timestamp=timestamp,
                camera_id=self.camera_id,
                metadata={
                    "anomaly_type": "CAMERA_FAILURE",
                    "severity": "HIGH",
                    "gap_seconds": round(gap, 1),
                },
            )
            logger.warning("anomaly_camera_failure", camera=self.camera_id, gap_s=gap)

    def _check_crowd_surge(self, engine: "EventEngine", timestamp: datetime) -> None:
        occupancy = engine.active_occupancy
        mean = engine.mean_occupancy
        if mean < 2:
            return
        key = f"crowd_surge_{self.camera_id}_{int(timestamp.timestamp() // 300)}"  # 5-min bucket
        if occupancy > mean * self.crowd_surge_ratio and key not in self._fired_anomalies:
            self._fired_anomalies.add(key)
            self.api.queue_event(
                event_type="ANOMALY",
                timestamp=timestamp,
                camera_id=self.camera_id,
                metadata={
                    "anomaly_type": "CROWD_SURGE",
                    "severity": "HIGH",
                    "current_occupancy": occupancy,
                    "mean_occupancy": round(mean, 1),
                    "ratio": round(occupancy / mean, 2),
                },
            )
            logger.warning("anomaly_crowd_surge", occupancy=occupancy, mean=mean)

    def _check_long_stay(self, engine: "EventEngine", timestamp: datetime) -> None:
        for tid, rec in engine._tracks.items():
            age_s = (timestamp - rec.first_seen).total_seconds()
            key = f"long_stay_{tid}"
            if age_s > self.long_stay_threshold_s and key not in self._fired_anomalies:
                self._fired_anomalies.add(key)
                self.api.queue_event(
                    event_type="ANOMALY",
                    timestamp=timestamp,
                    camera_id=self.camera_id,
                    track_id=tid,
                    session_id=rec.session_id,
                    metadata={
                        "anomaly_type": "LONG_STAY",
                        "severity": "MEDIUM",
                        "stay_seconds": round(age_s, 0),
                    },
                )
                logger.warning("anomaly_long_stay", tid=tid, stay_s=age_s)

    def _check_excess_reentry(self, engine: "EventEngine", timestamp: datetime) -> None:
        reentry_counts: dict[str, int] = {}
        for tid, rec in engine._tracks.items():
            if rec.reentry_count >= self.excess_reentry_count:
                reentry_counts[tid] = rec.reentry_count

        for tid, count in reentry_counts.items():
            key = f"excess_reentry_{tid}"
            if key not in self._fired_anomalies:
                self._fired_anomalies.add(key)
                rec = engine._tracks[tid]
                self.api.queue_event(
                    event_type="ANOMALY",
                    timestamp=timestamp,
                    camera_id=self.camera_id,
                    track_id=tid,
                    session_id=rec.session_id,
                    metadata={
                        "anomaly_type": "EXCESS_REENTRY",
                        "severity": "MEDIUM",
                        "reentry_count": count,
                    },
                )
                logger.warning("anomaly_excess_reentry", tid=tid, count=count)
