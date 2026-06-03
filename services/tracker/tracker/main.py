"""
Tracker service entry point.

For each video file (or RTSP stream):
  1. Ingestor yields frames
  2. Detector runs YOLOv11 + ByteTrack → detections
  3. EventEngine converts detections → business events
  4. AnomalyRulesEngine checks for anomalies
  5. ApiClient batches & flushes events to FastAPI
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog

from tracker.anomaly_rules import AnomalyRulesEngine
from tracker.api_client import ApiClient
from tracker.config import get_settings
from tracker.detector import Detector
from tracker.event_engine import EventEngine
from tracker.ingestor import VideoIngestor
from tracker.zone_engine import Zone, ZoneEngine
from shapely.geometry import Polygon

logger = structlog.get_logger(__name__)

# Hardcoded zone config derived from parse_layout.py analysis.
# In production, fetched from /api/v1/zones at startup.
_DEFAULT_ZONES = [
    {"id": "zone_entrance",    "name": "Entrance",       "zone_type": "ENTRANCE",
     "polygon": [[0.0,0.85],[0.18,0.85],[0.18,1.0],[0.0,1.0]]},
    {"id": "zone_exit",        "name": "Exit/Checkout",  "zone_type": "EXIT",
     "polygon": [[0.82,0.85],[1.0,0.85],[1.0,1.0],[0.82,1.0]]},
    {"id": "zone_skincare_row","name": "Skincare Row",   "zone_type": "PRODUCT",
     "polygon": [[0.0,0.0],[1.0,0.0],[1.0,0.3],[0.0,0.3]]},
    {"id": "zone_makeup_row",  "name": "Makeup Row",     "zone_type": "PRODUCT",
     "polygon": [[0.0,0.5],[1.0,0.5],[1.0,0.85],[0.0,0.85]]},
    {"id": "zone_aisle",       "name": "Centre Aisle",  "zone_type": "WALKWAY",
     "polygon": [[0.0,0.3],[1.0,0.3],[1.0,0.5],[0.0,0.5]]},
]


def build_zone_engine(zones_cfg: list[dict]) -> ZoneEngine:
    zones = [
        Zone(
            id=z["id"],
            name=z["name"],
            zone_type=z["zone_type"],
            polygon=Polygon(z["polygon"]),
        )
        for z in zones_cfg
    ]
    return ZoneEngine(zones)


async def process_video(
    video_path: Path,
    camera_id: str,
    api: ApiClient,
    settings,
) -> None:
    zone_engine = build_zone_engine(_DEFAULT_ZONES)
    event_eng = EventEngine(
        api=api,
        zone_engine=zone_engine,
        camera_id=camera_id,
        dwell_threshold_s=settings.dwell_threshold_s,
    )
    anomaly_eng = AnomalyRulesEngine(
        api=api,
        camera_id=camera_id,
        crowd_surge_ratio=settings.crowd_surge_ratio,
        long_stay_threshold_s=settings.long_stay_threshold_s,
        excess_reentry_count=settings.excess_reentry_count,
        camera_freeze_threshold_s=settings.camera_freeze_threshold_s,
    )
    ingestor = VideoIngestor(
        video_dir=str(video_path.parent),
        process_every_n=settings.process_every_n_frames,
    )
    detector = Detector(
        model_path=settings.yolo_model,
        conf=settings.yolo_conf,
        iou=settings.yolo_iou,
    )

    logger.info("start_video", camera=camera_id, file=video_path.name)

    for frame, fw, fh, fn in ingestor.frames(video_path):
        # Use monotonic frame time — map to real timestamp using video fps
        timestamp = datetime.now(timezone.utc)  # real-time processing
        detections = detector.detect_and_track(frame)

        if detections:
            anomaly_eng.on_frame_with_detections(timestamp)

        event_eng.update(detections, fw, fh, timestamp)
        anomaly_eng.run(event_eng, timestamp)
        anomaly_eng.check_camera_freeze(timestamp)

        # Yield control every 10 frames so API flush can run
        if fn % 10 == 0:
            await asyncio.sleep(0)

    logger.info("video_complete", camera=camera_id, file=video_path.name)


async def main() -> None:
    settings = get_settings()

    api = ApiClient(
        base_url=settings.api_base_url,
        batch_size=50,
        flush_interval=1.0,
    )
    await api.start()

    try:
        video_dir = Path(settings.video_dir)
        mp4_files = sorted(video_dir.glob("*.mp4"))

        if not mp4_files:
            logger.warning("no_videos_found", dir=str(video_dir))
            return

        logger.info("found_videos", count=len(mp4_files))

        tasks = []
        for i, vf in enumerate(mp4_files):
            camera_id = f"cam_{i+1}"
            tasks.append(process_video(vf, camera_id, api, settings))

        # Process cameras concurrently (async, but detector is sync — runs in executor)
        await asyncio.gather(*tasks)

    finally:
        await api.stop()
        logger.info("tracker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
